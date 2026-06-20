import { useCallback, useEffect, useRef, useState } from "react";
import { getHistory, streamChat, type Message } from "../api/client";
import { applyTool } from "../api/activity";
import { prependEarlier } from "../chat/scrollback";
import { useT } from "../i18n";

// The chat view is a bounded scroll-back: a small first page, more loaded as you
// scroll up, until CAP — past that, the diary is the way further back.
const INITIAL_LOAD = 30;
const PAGE = 30;
const CAP = 100;

export function useChat() {
  const { t } = useT();
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [canLoadEarlier, setCanLoadEarlier] = useState(false);
  const [cappedEarlier, setCappedEarlier] = useState(false);
  const streamingRef = useRef(false);
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
    streamingRef.current = true;
    setStreaming(true);
    const patch = (fn: (msg: Message) => Message) =>
      setMessages((m) => m.map((msg) => (msg.turn === asstTurn ? fn(msg) : msg)));
    try {
      await streamChat(text, {
        onDelta: (delta) => patch((msg) => ({ ...msg, content: msg.content + delta })),
        onReasoning: (r) => patch((msg) => ({ ...msg, reasoning: (msg.reasoning ?? "") + r })),
        onTool: (ev) => patch((msg) => ({ ...msg, activity: applyTool(msg.activity, ev) })),
      });
    } catch (e) {
      console.error("chat stream failed", e);
      setMessages((m) =>
        m.map((msg) =>
          msg.turn === asstTurn ? { ...msg, content: t("chat.error") } : msg,
        ),
      );
    } finally {
      streamingRef.current = false;
      setStreaming(false);
    }
  }

  return { messages, streaming, send, loadEarlier, canLoadEarlier, cappedEarlier };
}
