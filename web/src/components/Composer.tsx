import { useLayoutEffect, useRef, useState } from "react";
import { useT } from "../i18n";

const MAX_H = 240; // ~10 lines, then the area scrolls internally

// Send shortcut is ⌘+Enter on Mac, Ctrl+Enter elsewhere; Enter alone is a newline.
const IS_MAC =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);
const SEND_KEY = IS_MAC ? "⌘+Enter" : "Ctrl+Enter";

// Prompt-side modes offered in the footer switch. Each value must match a persona
// folder name on the backend; the label is an i18n key under `composer.mode.*`.
const MODES = ["neutral", "freud"] as const;

export function Composer({
  onSend,
  onStop,
  streaming,
  persona,
  onPersonaChange,
}: {
  onSend: (t: string) => void;
  onStop: () => void;
  streaming: boolean;
  persona?: string;
  onPersonaChange?: (p: string) => void;
}) {
  const { t: tr } = useT();
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // Grow the area to fit its content, capped — min-height keeps it a block when empty.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, MAX_H)}px`;
    el.style.overflowY = el.scrollHeight > MAX_H ? "auto" : "hidden";
  }, [text]);

  function submit() {
    const t = text.trim();
    if (streaming || !t) return;
    onSend(t);
    setText("");
  }

  return (
    <div className="border-t border-line bg-gradient-to-b from-transparent to-base">
      <div className="mx-auto w-full max-w-[58rem] px-5 py-4 sm:px-8 2xl:max-w-[60rem]">
        <div className="rounded-2xl border border-line bg-surface shadow-card transition-colors focus-within:border-accent/40 focus-within:ring-2 focus-within:ring-accent/15">
          <textarea
            ref={ref}
            className="block max-h-60 min-h-[84px] w-full resize-none bg-transparent px-4 pb-1.5 pt-3.5 text-sm leading-relaxed text-ink placeholder:text-muted focus:outline-none"
            rows={3}
            value={text}
            aria-label="Message"
            placeholder={tr("composer.placeholder")}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <div className="flex items-center justify-between gap-3 px-3 pb-2.5">
            <div className="flex min-w-0 items-center gap-2.5">
              {onPersonaChange && (
                <div
                  role="radiogroup"
                  aria-label={tr("composer.mode.label")}
                  className="inline-flex shrink-0 rounded-lg border border-line bg-base p-0.5 text-[11px] font-medium"
                >
                  {MODES.map((m) => {
                    const active = (persona ?? "neutral") === m;
                    return (
                      <button
                        key={m}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        onClick={() => onPersonaChange(m)}
                        className={
                          "rounded-md px-2.5 py-1 transition-colors " +
                          (active ? "bg-surface text-ink shadow-card" : "text-muted hover:text-ink")
                        }
                      >
                        {tr(`composer.mode.${m}`)}
                      </button>
                    );
                  })}
                </div>
              )}
              <span className="hidden select-none truncate text-[11px] text-muted sm:inline">
                {tr("composer.hint", { key: SEND_KEY })}
              </span>
            </div>
            {streaming ? (
              <button
                className="rounded-xl border border-line bg-surface px-5 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-accent/40 hover:text-ink"
                onClick={onStop}
              >
                {tr("composer.stop")}
              </button>
            ) : (
              <button
                className="rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-accent-fg shadow-[0_5px_16px_rgba(208,102,63,0.18)] transition-colors hover:bg-accent-ink disabled:opacity-40"
                onClick={submit}
                disabled={!text.trim()}
              >
                {tr("composer.send")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
