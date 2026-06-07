import { useEffect, useRef, useState } from "react";
import { getHistory, streamChat, type Message } from "../api/client";

export function useChat() {
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
    setMessages((m) => [
      ...m,
      { turn: userTurn, role: "user", content: text },
      { turn: asstTurn, role: "assistant", content: "" },
    ]);
    streamingRef.current = true;
    setStreaming(true);
    try {
      await streamChat(text, (delta) => {
        setMessages((m) =>
          m.map((msg) =>
            msg.turn === asstTurn ? { ...msg, content: msg.content + delta } : msg,
          ),
        );
      });
    } catch (e) {
      console.error("chat stream failed", e);
      setMessages((m) =>
        m.map((msg) =>
          msg.turn === asstTurn ? { ...msg, content: "⚠️ 出错了，请重试" } : msg,
        ),
      );
    } finally {
      streamingRef.current = false;
      setStreaming(false);
    }
  }

  return { messages, streaming, send };
}
