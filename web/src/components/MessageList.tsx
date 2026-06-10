import { useEffect, useRef } from "react";
import type { Message } from "../api/client";
import { MessageBubble } from "./MessageBubble";

export function MessageList({ messages }: { messages: Message[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="mx-auto flex max-w-[46rem] flex-col gap-7 px-6 py-10">
        {messages.map((m) => (
          <MessageBubble key={m.turn} m={m} />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
