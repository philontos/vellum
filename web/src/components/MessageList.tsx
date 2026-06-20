import { useEffect, useRef } from "react";
import type { Message } from "../api/client";
import { useT } from "../i18n";
import { MessageBubble } from "./MessageBubble";

/** "YYYY-MM-DD" for grouping; empty when no timestamp. */
function dayOf(ts?: string): string {
  return ts ? ts.slice(0, 10) : "";
}

function dayLabel(ts: string, lang: string): string {
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? ts.replace(" ", "T") : ts.replace(" ", "T") + "Z";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) return lang === "zh" ? "今天" : "Today";
  return lang === "zh"
    ? `${d.getMonth() + 1}月${d.getDate()}日`
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function MessageList({ messages, streaming }: { messages: Message[]; streaming: boolean }) {
  const { lang } = useT();
  const scrollRef = useRef<HTMLDivElement>(null);
  // Follow the stream only while the reader is parked at the bottom. Once they
  // scroll up to re-read, we never yank the viewport back — no auto-positioning.
  const pinned = useRef(true);
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };
  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight; // instant, no smooth re-centering
  }, [messages]);

  const lastIdx = messages.length - 1;
  let prevDay = "";

  return (
    <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-[58rem] flex-col gap-7 px-5 py-10 sm:px-8 2xl:max-w-[60rem]">
        {messages.map((m, i) => {
          const day = dayOf(m.created_at);
          const label = day && day !== prevDay ? dayLabel(m.created_at!, lang) : "";
          if (day) prevDay = day;
          return (
            <div key={m.turn} className="contents">
              {label && (
                <div className="v-timebreak" aria-hidden>
                  {label}
                </div>
              )}
              <MessageBubble m={m} latest={i === lastIdx} streaming={streaming} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
