import type { Message } from "../api/client";

export function MessageBubble({ m }: { m: Message }) {
  const mine = m.role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
          mine ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900"
        }`}
      >
        {m.content || "…"}
      </div>
    </div>
  );
}
