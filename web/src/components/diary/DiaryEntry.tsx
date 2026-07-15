import { useEffect, useRef, type RefObject } from "react";

import type { DiaryCard, Message } from "../../api/client";
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
  lang,
  scrollRef,
  onBack,
  onRetry,
}: {
  card: DiaryCard | null;
  state?: DiaryEntryState;
  lang: "en" | "zh";
  scrollRef: RefObject<HTMLDivElement>;
  onBack: () => void;
  onRetry: () => void;
}) {
  const { t } = useT();
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      titleRef.current?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [card?.id]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="flex-none border-b border-line bg-canvas/95 px-2 py-1.5 backdrop-blur sm:px-5 sm:py-2">
        <div className="relative mx-auto flex min-h-10 w-full max-w-[58rem] items-center justify-center px-12">
          <button
            type="button"
            aria-label={t("diary.back")}
            title={t("diary.back")}
            onClick={onBack}
            className="absolute left-0 flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10 text-accent-ink transition-colors hover:bg-accent/20 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
          >
            <span aria-hidden className="text-lg font-semibold leading-none">←</span>
          </button>
          <div className="min-w-0 max-w-full text-center">
            <h1
              ref={titleRef}
              tabIndex={-1}
              className="truncate font-serif text-base text-ink focus:outline-none"
            >
              {card ? dayLabel(card.created_at, lang) : t("diary.entryTitle")}
            </h1>
            {card && (
              <div className="truncate font-mono text-[10px] text-muted">
                {card.created_at?.slice(11, 16)} · {t("diary.span", {
                  start: card.start_turn,
                  end: card.end_turn,
                })}
              </div>
            )}
          </div>
        </div>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="mx-auto flex w-full max-w-[58rem] flex-col gap-7 px-4 py-6 sm:gap-9 sm:px-8 sm:py-9">
          {card && (
            <section className="rounded-xl border border-line bg-surface/70 px-4 py-4 sm:px-5">
              <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
                {t("diary.summary")}
              </div>
              <p className="text-[13.5px] leading-relaxed text-ink-soft">{card.content}</p>
            </section>
          )}

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
