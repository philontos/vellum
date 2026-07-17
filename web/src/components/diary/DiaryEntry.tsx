import {
  useEffect,
  useId,
  useRef,
  type KeyboardEvent as ReactKeyboardEvent,
  type RefObject,
} from "react";

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
  onClose,
  onRetry,
}: {
  card: DiaryCard | null;
  state?: DiaryEntryState;
  lang: "en" | "zh";
  scrollRef: RefObject<HTMLDivElement>;
  onClose: () => void;
  onRetry: () => void;
}) {
  const { t } = useT();
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus({ preventScroll: true });
    function escape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [onClose]);

  function trapFocus(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key !== "Tab") return;
    const focusable = Array.from(
      event.currentTarget.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      className="absolute inset-0 z-40 flex items-center justify-center bg-black/70 p-2 backdrop-blur-[2px] sm:p-6"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onKeyDown={trapFocus}
        className="flex h-full max-h-[48rem] min-h-0 w-full max-w-[58rem] flex-col overflow-hidden rounded-xl border border-line bg-canvas shadow-float sm:rounded-2xl"
      >
        <div aria-hidden className="h-px flex-none bg-gradient-to-r from-transparent via-gold/70 to-transparent" />
        <header className="flex-none border-b border-line bg-surface/95 px-2 py-1.5 backdrop-blur sm:px-4 sm:py-2">
          <div className="relative flex min-h-12 items-center justify-center px-12">
            <div className="min-w-0 max-w-full text-center">
              <h2 id={titleId} className="truncate font-serif text-base font-medium text-ink sm:text-lg">
                {card ? dayLabel(card.created_at, lang) : t("diary.entryTitle")}
              </h2>
              {card && (
                <div className="truncate font-mono text-[10px] text-muted">
                  {card.created_at?.slice(11, 16)} · {t("diary.span", {
                    start: card.start_turn,
                    end: card.end_turn,
                  })}
                </div>
              )}
            </div>
            <button
              ref={closeRef}
              type="button"
              aria-label={t("diary.close")}
              title={t("diary.close")}
              onClick={onClose}
              className="absolute right-0 flex h-10 w-10 items-center justify-center rounded-full border border-line bg-canvas text-muted transition-colors hover:border-accent/40 hover:bg-accent/10 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              <span aria-hidden className="text-base leading-none">✕</span>
            </button>
          </div>
        </header>

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <div className="mx-auto flex w-full max-w-[50rem] flex-col gap-7 px-4 py-5 sm:gap-9 sm:px-8 sm:py-8">
            {card && (
              <section className="rounded-xl border border-line border-l-2 border-l-gold/45 bg-surface/70 px-4 py-4 sm:px-5">
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
      </section>
    </div>
  );
}
