import type { RefObject } from "react";

import type { DiaryCard } from "../../api/client";
import type { DiaryDay } from "../../diary/group";
import { useT } from "../../i18n";
import { dayLabel } from "../../util/day";

const MODES = ["neutral", "freud"] as const;

export function DiaryTimeline({
  days,
  cardCount,
  stream,
  lang,
  loading,
  atEnd,
  scrollRef,
  bottomRef,
  onStreamChange,
  onOpen,
}: {
  days: DiaryDay[];
  cardCount: number;
  stream: string;
  lang: "en" | "zh";
  loading: boolean;
  atEnd: boolean;
  scrollRef: RefObject<HTMLDivElement>;
  bottomRef: RefObject<HTMLDivElement>;
  onStreamChange: (stream: string) => void;
  onOpen: (card: DiaryCard) => void;
}) {
  const { t } = useT();

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
        <span className="text-sm text-muted">{t("diary.sub")}</span>
        <div
          role="radiogroup"
          aria-label={t("composer.mode.label")}
          className="inline-flex shrink-0 rounded-lg border border-line bg-base p-0.5 text-[11px] font-medium"
        >
          {MODES.map((mode) => {
            const active = stream === mode;
            return (
              <button
                key={mode}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => onStreamChange(mode)}
                className={
                  "rounded-md px-2.5 py-1 transition-colors " +
                  (active ? "bg-surface text-ink shadow-card" : "text-muted hover:text-ink")
                }
              >
                {t(`composer.mode.${mode}`)}
              </button>
            );
          })}
        </div>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <div className="mx-auto flex w-full max-w-[52rem] flex-col gap-5 px-4 py-6 sm:px-5 sm:py-8">
          {days.map((day) => (
            <div key={day.day} className="flex flex-col gap-3">
              <div className="v-timebreak" aria-hidden>
                {day.day ? dayLabel(day.cards[0].created_at, lang) : ""}
              </div>
              {day.cards.map((card) => (
                <button
                  key={card.id}
                  type="button"
                  data-diary-card={card.id}
                  onClick={() => onOpen(card)}
                  className="group/entry w-full rounded-xl border border-line bg-surface px-4 py-3 text-left transition-colors hover:border-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
                >
                  <span className="flex items-start gap-3">
                    <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-gold" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13.5px] leading-[1.6] text-ink-soft">
                        {card.content}
                      </span>
                      <span className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-[11px] text-muted">
                        <span>
                          {card.created_at?.slice(11, 16)} · {t("diary.span", {
                            start: card.start_turn,
                            end: card.end_turn,
                          })}
                        </span>
                        <span className="ml-auto inline-flex items-center gap-1 font-sans text-accent transition-colors group-hover/entry:text-accent-ink">
                          {t("diary.read")}
                          <span aria-hidden>→</span>
                        </span>
                      </span>
                    </span>
                  </span>
                </button>
              ))}
            </div>
          ))}

          {cardCount === 0 && !loading && (
            <div className="p-4 text-muted sm:p-8">{t("diary.empty")}</div>
          )}
          <div ref={bottomRef} aria-hidden className="h-px" />
          {loading && <div className="py-4 text-center text-xs text-muted">{t("diary.loading")}</div>}
          {atEnd && cardCount > 0 && (
            <div className="py-4 text-center text-xs text-muted">{t("diary.end")}</div>
          )}
        </div>
      </div>
    </div>
  );
}
