import { useLayoutEffect, useRef, useState } from "react";
import { useT } from "../i18n";

const MAX_H = 240; // ~10 lines, then the area scrolls internally

// Send shortcut is ⌘+Enter on Mac, Ctrl+Enter elsewhere; Enter alone is a newline.
const IS_MAC =
  typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);
const SEND_KEY = IS_MAC ? "⌘+Enter" : "Ctrl+Enter";

export function Composer({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
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
    if (disabled || !t) return;
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
            <span className="select-none pl-1 text-[11px] text-muted">
              {tr("composer.hint", { key: SEND_KEY })}
            </span>
            <button
              className="rounded-xl bg-accent px-5 py-2 text-sm font-semibold text-accent-fg shadow-[0_5px_16px_rgba(208,102,63,0.18)] transition-colors hover:bg-accent-ink disabled:opacity-40"
              onClick={submit}
              disabled={disabled || !text.trim()}
            >
              {tr("composer.send")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
