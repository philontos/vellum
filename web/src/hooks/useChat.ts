import { useEffect, useRef, useState } from "react";
import { getHistory, streamChat, type Message } from "../api/client";
import { applyTool } from "../api/activity";
import { useT } from "../i18n";

export function useChat() {
  const { t } = useT();
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const streamingRef = useRef(false);
  const nextTurn = useRef(0);

  useEffect(() => {
    getHistory()
      .then((m) => {
        if (streamingRef.current) return; // don't clobber an in-flight stream
        setMessages(m);
        nextTurn.current = m.length ? m[m.length - 1].turn + 1 : 0;
      })
      .catch((e) => console.error("history load failed", e));
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

  return { messages, streaming, send };
}
