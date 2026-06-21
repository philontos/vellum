import { useEffect, useLayoutEffect, useRef } from "react";
import type { Message } from "../api/client";
import { useT } from "../i18n";
import { dayOf, dayLabel } from "../util/day";
import { MessageBubble } from "./MessageBubble";

export function MessageList({
  messages,
  streaming,
  onRetry,
  onDelete,
  canLoadEarlier = false,
  cappedEarlier = false,
  onLoadEarlier,
  onOpenDiary,
}: {
  messages: Message[];
  streaming: boolean;
  onRetry?: (turn: number) => void;
  onDelete?: (turn: number) => void;
  canLoadEarlier?: boolean;
  cappedEarlier?: boolean;
  onLoadEarlier?: () => void;
  onOpenDiary?: () => void;
}) {
  const { t, lang } = useT();
  const scrollRef = useRef<HTMLDivElement>(null);
  const topRef = useRef<HTMLDivElement>(null);
  // Auto-follow the stream by default, but the instant the reader scrolls up we
  // latch it off for the rest of this turn — we never grab the viewport back,
  // not even if they scroll to the bottom again. Only a fresh turn appended below
  // (sending a new message) re-arms the follow. Our own follow only ever scrolls
  // *down*, so any decrease in scrollTop is the reader taking over.
  const pinned = useRef(true);
  const lastTop = useRef(0);
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    if (el.scrollTop < lastTop.current) pinned.current = false;
    lastTop.current = el.scrollTop;
  };

  // One layout pass per message change: when an OLDER batch is prepended
  // (scroll-up) hold the reader's position; otherwise, while still pinned,
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
    // A new turn appended below (a send, or the initial load) re-arms auto-follow.
    // Streaming deltas patch the existing message in place, so the count is
    // unchanged and a mid-turn scroll-up stays latched off.
    if (messages.length > prevLen.current && !grewAtTop) pinned.current = true;
    if (grewAtTop) {
      el.scrollTop += el.scrollHeight - prevHeight.current; // keep the same content under the viewport
    } else if (pinned.current) {
      el.scrollTop = el.scrollHeight; // instant, no smooth re-centering
    }
    lastTop.current = el.scrollTop; // our own move is the new baseline, never an "upward" nudge
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
              <MessageBubble
                m={m}
                latest={i === lastIdx}
                streaming={streaming}
                onRetry={onRetry ? () => onRetry(m.turn) : undefined}
                onDelete={onDelete}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
