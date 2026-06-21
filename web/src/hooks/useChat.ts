import { useCallback, useEffect, useRef, useState } from "react";
import { getHistory, streamChat, deleteMessage, type Message } from "../api/client";
import { applyTool } from "../api/activity";
import { prependEarlier } from "../chat/scrollback";
import { removeTurn } from "../chat/remove";

// The chat view is a bounded scroll-back: a small first page, more loaded as you
// scroll up, until CAP — past that, the diary is the way further back.
const INITIAL_LOAD = 30;
const PAGE = 30;
const CAP = 100;

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [canLoadEarlier, setCanLoadEarlier] = useState(false);
  const [cappedEarlier, setCappedEarlier] = useState(false);
  const streamingRef = useRef(false);
  const ctrlRef = useRef<AbortController | null>(null); // the in-flight stream's stop handle
  const nextTurn = useRef(0);

  // Scroll-up paging state (refs so loadEarlier can stay a stable callback).
  const messagesRef = useRef<Message[]>([]);
  const oldestTurn = useRef<number | null>(null);
  const loadingEarlier = useRef(false);
  const atStart = useRef(false);
  const atCap = useRef(false);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    getHistory({ limit: INITIAL_LOAD })
      .then((m) => {
        if (streamingRef.current) return; // don't clobber an in-flight stream
        setMessages(m);
        oldestTurn.current = m.length ? m[0].turn : null;
        nextTurn.current = m.length ? m[m.length - 1].turn + 1 : 0;
        atStart.current = m.length < INITIAL_LOAD;
        setCanLoadEarlier(!atStart.current);
      })
      .catch((e) => console.error("history load failed", e));
  }, []);

  const loadEarlier = useCallback(async () => {
    if (loadingEarlier.current || atCap.current || atStart.current) return;
    const before = oldestTurn.current;
    if (before === null || before <= 0) {
      atStart.current = true;
      setCanLoadEarlier(false);
      return;
    }
    loadingEarlier.current = true;
    try {
      const older = await getHistory({ before, limit: PAGE });
      if (older.length === 0) {
        atStart.current = true;
        setCanLoadEarlier(false);
        return;
      }
      const { messages: merged, atCap: capped } = prependEarlier(messagesRef.current, older, CAP);
      atCap.current = capped;
      if (older.length < PAGE) atStart.current = true;
      oldestTurn.current = merged.length ? merged[0].turn : oldestTurn.current;
      setMessages(merged);
      setCappedEarlier(capped);
      setCanLoadEarlier(!atCap.current && !atStart.current);
    } catch (e) {
      console.error("load earlier failed", e);
    } finally {
      loadingEarlier.current = false;
    }
  }, []);

  // Stream one reply into the assistant bubble at `asstTurn`. Shared by send and
  // retry. A manual stop (AbortError) keeps whatever streamed so far without
  // flagging failure; any other error flags the bubble so the UI offers a retry.
  async function runStream(text: string, asstTurn: number) {
    streamingRef.current = true;
    setStreaming(true);
    const ctrl = new AbortController();
    ctrlRef.current = ctrl;
    const patch = (fn: (msg: Message) => Message) =>
      setMessages((m) => m.map((msg) => (msg.turn === asstTurn ? fn(msg) : msg)));
    try {
      await streamChat(
        text,
        {
          onDelta: (delta) => patch((msg) => ({ ...msg, content: msg.content + delta })),
          onReasoning: (r) => patch((msg) => ({ ...msg, reasoning: (msg.reasoning ?? "") + r })),
          onTool: (ev) => patch((msg) => ({ ...msg, activity: applyTool(msg.activity, ev) })),
        },
        { signal: ctrl.signal },
      );
    } catch (e) {
      if ((e as Error)?.name === "AbortError") return; // manual stop — keep partial reply, no error
      console.error("chat stream failed", e);
      patch((msg) => ({ ...msg, failed: true }));
    } finally {
      streamingRef.current = false;
      setStreaming(false);
      ctrlRef.current = null;
    }
  }

  async function send(text: string) {
    if (!text.trim() || streamingRef.current) return;
    const userTurn = nextTurn.current++;
    const asstTurn = nextTurn.current++;
    const now = new Date().toISOString();
    setMessages((m) => [
      ...m,
      { turn: userTurn, role: "user", content: text, created_at: now },
      { turn: asstTurn, role: "assistant", content: "", created_at: now },
    ]);
    await runStream(text, asstTurn);
  }

  // Stop the in-flight stream. The reply streamed so far stays put; the composer
  // re-enables so the reader can send again — no page reload needed.
  function stop() {
    ctrlRef.current?.abort();
  }

  // Re-run a failed turn in place: reuse the same assistant bubble (no duplicate
  // user message, turn numbers unchanged) and re-stream its preceding user text.
  function retry(asstTurn: number) {
    if (streamingRef.current) return;
    const msgs = messagesRef.current;
    const idx = msgs.findIndex((m) => m.turn === asstTurn);
    if (idx <= 0) return;
    const user = msgs[idx - 1];
    if (user.role !== "user") return;
    setMessages((m) =>
      m.map((msg) =>
        msg.turn === asstTurn
          ? { ...msg, content: "", reasoning: undefined, activity: undefined, failed: false }
          : msg,
      ),
    );
    void runStream(user.content, asstTurn);
  }

  // Soft-delete a stray turn (failed retry, debug noise): tell the server, then
  // take it out of the view. The server keeps the row, so it's reversible; we
  // only drop it here once the delete is acknowledged.
  const remove = useCallback(async (turn: number) => {
    try {
      await deleteMessage(turn);
      setMessages((m) => removeTurn(m, turn));
    } catch (e) {
      console.error("delete message failed", e);
    }
  }, []);

  return { messages, streaming, send, stop, retry, remove, loadEarlier, canLoadEarlier, cappedEarlier };
}
