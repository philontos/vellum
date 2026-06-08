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
    <div className="flex gap-2 border-t border-gray-200 p-3">
      <textarea
        className="flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring"
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
        className="rounded-xl bg-blue-600 px-4 text-sm font-medium text-white disabled:opacity-40"
        onClick={submit}
        disabled={disabled}
      >
        {tr("composer.send")}
      </button>
    </div>
  );
}
