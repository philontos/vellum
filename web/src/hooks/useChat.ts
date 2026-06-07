import { useEffect, useRef, useState } from "react";
import { getHistory, streamChat, type Message } from "../api/client";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const nextTurn = useRef(0);

  useEffect(() => {
    getHistory()
      .then((m) => {
        setMessages(m);
        nextTurn.current = m.length ? m[m.length - 1].turn + 1 : 0;
      })
      .catch(() => void 0);
  }, []);

  async function send(text: string) {
    if (!text.trim() || streaming) return;
    const userTurn = nextTurn.current++;
    const asstTurn = nextTurn.current++;
    setMessages((m) => [
      ...m,
      { turn: userTurn, role: "user", content: text },
      { turn: asstTurn, role: "assistant", content: "" },
    ]);
    setStreaming(true);
    try {
      await streamChat(text, (delta) => {
        setMessages((m) =>
          m.map((msg) =>
            msg.turn === asstTurn ? { ...msg, content: msg.content + delta } : msg,
          ),
        );
      });
    } finally {
      setStreaming(false);
    }
  }

  return { messages, streaming, send };
}
