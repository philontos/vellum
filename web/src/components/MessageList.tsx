import { useEffect, useLayoutEffect, useRef } from "react";
import type { Message } from "../api/client";
import { useT } from "../i18n";
import { dayOf, dayLabel } from "../util/day";
import { MessageBubble } from "./MessageBubble";

export function MessageList({
  messages,
  streaming,
  canLoadEarlier = false,
  cappedEarlier = false,
  onLoadEarlier,
  onOpenDiary,
}: {
  messages: Message[];
  streaming: boolean;
  canLoadEarlier?: boolean;
  cappedEarlier?: boolean;
  onLoadEarlier?: () => void;
  onOpenDiary?: () => void;
}) {
  const { t, lang } = useT();
  const scrollRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);
  // Follow the stream only while the reader is parked at the bottom. Once they
  // scroll up to re-read, we never yank the viewport back — no auto-positioning.
  const pinned = useRef(true);
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  // One layout pass per message change: when an OLDER batch is prepended
  // (scroll-up) hold the reader's position; otherwise, if parked at the bottom,
  // follow the stream. The two never fight — a prepend means we're up top.
  const prevFirstTurn = useRef<number | undefined>(undefined);
  const prevLen = useRef(0);
  const prevHeight = useRef(0);
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const first = messages[0]?.turn;
    const grewAtTop =
      messages.length > prevLen.current &&
      first !== undefined &&
      prevFirstTurn.current !== undefined &&
      first < prevFirstTurn.current;
    if (grewAtTop) {
      el.scrollTop += el.scrollHeight - prevHeight.current; // keep the same content under the viewport
    } else if (pinned.current) {
      el.scrollTop = el.scrollHeight; // instant, no smooth re-centering
    }
    prevFirstTurn.current = first;
    prevLen.current = messages.length;
    prevHeight.current = el.scrollHeight;
  }, [messages]);

  // Fetch the previous page when the top sentinel becomes visible.
  useEffect(() => {
    const top = topRef.current;
    const root = scrollRef.current;
    if (!top || !root || !canLoadEarlier || !onLoadEarlier) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) onLoadEarlier();
      },
      { root },
    );
    obs.observe(top);
    return () => obs.disconnect();
  }, [canLoadEarlier, onLoadEarlier, messages.length]);

  const lastIdx = messages.length - 1;
  let prevDay = "";

  return (
    <div ref={scrollRef} onScroll={onScroll} className="flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-[58rem] flex-col gap-7 px-5 py-10 sm:px-8 2xl:max-w-[60rem]">
        <div ref={topRef} aria-hidden className="h-px" />
        {cappedEarlier && (
          <button
            type="button"
            onClick={onOpenDiary}
            className="v-timebreak text-accent transition-colors hover:text-accent-ink"
          >
            {t("chat.olderInDiary")}
          </button>
        )}
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
