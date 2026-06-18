import { useState } from "react";
import { useT } from "../i18n";

export function Composer({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const { t: tr } = useT();
  const [text, setText] = useState("");
  function submit() {
    const t = text.trim();
    if (!t) return;
    onSend(t);
    setText("");
  }
  return (
    <div className="border-t border-line bg-gradient-to-b from-transparent to-base">
      <div className="mx-auto flex max-w-[46rem] items-end gap-3 px-6 py-4">
        <textarea
          className="flex-1 resize-none rounded-[13px] border border-line bg-surface px-4 py-3 text-sm text-ink placeholder:text-muted focus:border-accent/40 focus:outline-none focus:ring-2 focus:ring-accent/15"
          rows={1}
          value={text}
          aria-label="Message"
          placeholder={tr("composer.placeholder")}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button
          className="rounded-[13px] bg-accent px-5 py-3 text-sm font-semibold text-accent-fg shadow-[0_5px_16px_rgba(208,102,63,0.18)] transition-colors hover:bg-accent-ink disabled:opacity-40"
          onClick={submit}
          disabled={disabled}
        >
          {tr("composer.send")}
        </button>
      </div>
    </div>
  );
}
