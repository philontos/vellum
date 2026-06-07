import { useEffect, useRef } from "react";
import type { Message } from "../api/client";
import { MessageBubble } from "./MessageBubble";

export function MessageList({ messages }: { messages: Message[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  return (
    <div className="flex-1 space-y-3 overflow-y-auto px-4 py-6">
      {messages.map((m) => (
        <MessageBubble key={m.turn} m={m} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
