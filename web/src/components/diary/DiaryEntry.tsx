import { useEffect, useRef, type RefObject, type TouchEvent } from "react";

import type { DiaryCard, Message } from "../../api/client";
import { isDiaryBackSwipe, type TouchPoint } from "../../diary/navigation";
import { useT } from "../../i18n";
import { dayLabel } from "../../util/day";
import { MessageBubble } from "../MessageBubble";

export type DiaryEntryState =
  | { status: "loading"; messages: Message[] }
  | { status: "ready"; messages: Message[] }
  | { status: "error"; messages: Message[] };

export function DiaryEntry({
  card,
  state,
  active,
  lang,
  scrollRef,
  onBack,
  onRetry,
}: {
  card: DiaryCard | null;
  state?: DiaryEntryState;
  active: boolean;
  lang: "en" | "zh";
  scrollRef: RefObject<HTMLDivElement>;
  onBack: () => void;
  onRetry: () => void;
}) {
  const { t } = useT();
  const touchStart = useRef<TouchPoint | null>(null);
  const backRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!active || !card) return;
    const frame = requestAnimationFrame(() => backRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [active, card]);

  if (!card) return <div className="h-full" />;

  function startSwipe(event: TouchEvent) {
    const touch = event.touches[0];
    if (event.touches.length !== 1 || !touch) return;
    touchStart.current = { x: touch.clientX, y: touch.clientY };
  }

  function finishSwipe(event: TouchEvent) {
    const start = touchStart.current;
    const touch = event.changedTouches[0];
    touchStart.current = null;
    if (!start || !touch) return;
    if (isDiaryBackSwipe(start, { x: touch.clientX, y: touch.clientY })) onBack();
  }

  return (
    <div
      className="flex h-full min-h-0 touch-pan-y flex-col"
      onTouchStart={startSwipe}
      onTouchEnd={finishSwipe}
      onTouchCancel={() => {
        touchStart.current = null;
      }}
    >
      <div className="flex flex-none items-center gap-3 border-b border-line bg-base/95 px-3 py-2.5 backdrop-blur sm:px-5 sm:py-3">
        <button
          ref={backRef}
          type="button"
          onClick={onBack}
          className="flex min-h-10 flex-none items-center gap-1.5 rounded-lg px-2.5 text-sm text-ink-soft transition-colors hover:bg-surface hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
        >
          <span aria-hidden className="text-base">←</span>
          {t("diary.back")}
        </button>
        <div className="min-w-0 border-l border-line pl-3">
          <div className="truncate font-serif text-base text-ink">
            {dayLabel(card.created_at, lang)}
          </div>
          <div className="truncate font-mono text-[10px] text-muted">
            {card.created_at?.slice(11, 16)} · {t("diary.span", {
              start: card.start_turn,
              end: card.end_turn,
            })}
          </div>
        </div>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="mx-auto flex w-full max-w-[58rem] flex-col gap-7 px-4 py-6 sm:gap-9 sm:px-8 sm:py-9">
          <section className="rounded-xl border border-line bg-surface/70 px-4 py-4 sm:px-5">
            <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
              {t("diary.summary")}
            </div>
            <p className="text-[13.5px] leading-relaxed text-ink-soft">{card.content}</p>
          </section>

          <div className="flex flex-col gap-6 sm:gap-7">
            {(state?.messages ?? []).map((message) => (
              <MessageBubble
                key={message.turn}
                m={message}
                latest={false}
                streaming={false}
              />
            ))}
            {(!state || state.status === "loading") && (
              <div className="py-8 text-center text-xs text-muted">{t("diary.loading")}</div>
            )}
            {state?.status === "error" && (
              <div role="alert" className="rounded-xl border border-line bg-surface px-4 py-5 text-center">
                <div className="text-sm text-ink-soft">{t("diary.loadFailed")}</div>
                <button
                  type="button"
                  onClick={onRetry}
                  className="mt-3 min-h-10 rounded-lg border border-line px-4 text-sm text-accent transition-colors hover:border-accent/50 hover:text-accent-ink"
                >
                  {t("diary.retry")}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
