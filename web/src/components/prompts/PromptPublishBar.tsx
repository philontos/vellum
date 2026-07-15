import { useT } from "../../i18n";
import type { PromptBusy } from "./PromptEditor";

export function PromptPublishBar({
  note,
  busy,
  disabled,
  blocker,
  onNoteChange,
  onPublish,
}: {
  note: string;
  busy: PromptBusy;
  disabled: boolean;
  blocker: string;
  onNoteChange: (note: string) => void;
  onPublish: () => void;
}) {
  const { t } = useT();

  return (
    <section className="rounded-xl border border-line bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-[14rem] flex-1">
          <span className="mb-1 block text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
            {t("prompts.releaseNote")}
          </span>
          <input
            value={note}
            disabled={busy !== null}
            onChange={(event) => onNoteChange(event.target.value)}
            placeholder={t("prompts.releaseNotePh")}
            className="min-h-11 w-full rounded-lg border border-line bg-well px-3 text-base text-ink-soft placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/20 sm:text-sm disabled:opacity-60"
          />
        </label>
        <button
          type="button"
          disabled={disabled}
          onClick={onPublish}
          className="min-h-11 rounded-lg bg-accent px-4 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-ink disabled:cursor-not-allowed disabled:bg-well disabled:text-muted disabled:opacity-70"
        >
          {busy === "publish" ? t("prompts.publishing") : t("prompts.publish")}
        </button>
      </div>
      <div aria-live="polite" className="mt-1.5 min-h-4 text-xs text-muted">
        {blocker}
      </div>
    </section>
  );
}
