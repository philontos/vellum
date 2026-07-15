import { useId, type KeyboardEvent } from "react";

import { useT } from "../../i18n";

export function FactEditor({
  draft,
  error,
  busy,
  onDraft,
  onSave,
  onCancel,
  onLeave,
}: {
  draft: string;
  error: string;
  busy: boolean;
  onDraft: (text: string) => void;
  onSave: () => void;
  onCancel: () => void;
  onLeave: () => void;
}) {
  const { t } = useT();
  const errorId = useId();

  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    } else if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      onSave();
    }
  }

  return (
    <li
      data-editing="true"
      onBlur={(event) => {
        const next = event.relatedTarget as Node | null;
        if (next && event.currentTarget.contains(next)) return;
        onLeave();
      }}
      className="rounded-xl border border-accent/50 bg-surface px-4 py-3 shadow-card"
    >
      <textarea
        autoFocus
        rows={5}
        value={draft}
        disabled={busy}
        aria-label={t("model.factEditField")}
        aria-invalid={!!error}
        aria-describedby={error ? errorId : undefined}
        onChange={(event) => onDraft(event.target.value)}
        onKeyDown={keyDown}
        className="min-h-32 w-full resize-y rounded-lg border border-line bg-well px-3 py-2.5 text-sm leading-relaxed text-ink outline-none transition-colors focus:border-accent/70 disabled:opacity-60"
      />
      <div className="mt-2 flex min-h-7 items-center justify-between gap-3">
        <div id={errorId} aria-live="polite" className="text-xs text-status-fail-fg">
          {error}
        </div>
        <div className="flex flex-none items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onCancel}
            className="rounded-lg px-3 py-1.5 text-xs text-muted transition-colors hover:bg-well hover:text-ink disabled:opacity-50"
          >
            {t("model.factCancel")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={onSave}
            className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-accent/85 disabled:opacity-50"
          >
            {t("model.factSave")}
          </button>
        </div>
      </div>
    </li>
  );
}
