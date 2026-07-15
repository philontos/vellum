import type { ManagedPrompt } from "../../api/prompts";
import { useT } from "../../i18n";
import { ReadingBlock } from "../ui/ReadingBlock";
import { Tag } from "../ui/StatusChip";

export type PromptBusy = "refresh" | "save" | "publish" | "restore" | null;

export function PromptEditor({
  prompt,
  draft,
  dirty,
  busy,
  onDraftChange,
  onSave,
}: {
  prompt: ManagedPrompt;
  draft: string;
  dirty: boolean;
  busy: PromptBusy;
  onDraftChange: (content: string) => void;
  onSave: () => void;
}) {
  const { t } = useT();
  const editorDisabled = busy !== null || !prompt.editable;

  return (
    <section className="min-w-0 rounded-xl border border-line bg-surface p-4 shadow-card sm:p-5">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-serif text-xl text-ink">{prompt.name}</h2>
            <Tag>{prompt.category}</Tag>
            <Tag>{prompt.template_format}</Tag>
            {!prompt.editable && <Tag>{t("prompts.readOnly")}</Tag>}
          </div>
          <div className="mt-1 font-mono text-[11px] text-muted">{prompt.key}</div>
          {prompt.description && (
            <p className="mt-2 text-sm leading-relaxed text-ink-soft">{prompt.description}</p>
          )}
        </div>
        <div className="text-right text-[10px] text-muted">
          {prompt.updated_at
            ? t("prompts.updated", { time: prompt.updated_at })
            : t("prompts.never")}
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
          {t("prompts.variables")}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {prompt.variables.length > 0 ? (
            prompt.variables.map((variable) => <Tag key={variable}>{variable}</Tag>)
          ) : (
            <span className="text-xs text-muted">{t("prompts.noVariables")}</span>
          )}
        </div>
      </div>

      {prompt.validation_errors.length > 0 && (
        <div className="mt-4 rounded-lg border border-status-fail-fg/30 bg-status-fail-bg px-3 py-2.5">
          <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-status-fail-fg">
            {t("prompts.validation")}
          </div>
          <ul className="mt-1 list-disc space-y-1 pl-4 text-xs text-status-fail-fg">
            {prompt.validation_errors.map((error) => <li key={error}>{error}</li>)}
          </ul>
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <label htmlFor="prompt-draft" className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
          {t("prompts.draft")}
        </label>
        {dirty && <span className="text-[10px] text-status-warn-fg">{t("prompts.unsaved")}</span>}
        <button
          type="button"
          disabled={editorDisabled || !dirty}
          onClick={onSave}
          className="ml-auto min-h-10 rounded-lg bg-accent px-3.5 py-1.5 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-ink disabled:cursor-not-allowed disabled:bg-well disabled:text-muted disabled:opacity-70"
        >
          {busy === "save" ? t("prompts.saving") : t("prompts.save")}
        </button>
      </div>
      <textarea
        id="prompt-draft"
        aria-label={t("prompts.draft")}
        value={draft}
        disabled={editorDisabled}
        onChange={(event) => onDraftChange(event.target.value)}
        spellCheck={false}
        className="mt-2 min-h-[24rem] w-full resize-y rounded-lg border border-line bg-well p-3 font-mono text-sm leading-relaxed text-ink-soft focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:cursor-not-allowed disabled:opacity-70"
      />

      <details className="mt-4 rounded-lg border border-line bg-well px-3 py-2">
        <summary className="cursor-pointer text-xs text-muted">{t("prompts.publishedContent")}</summary>
        <div className="mt-3">
          <ReadingBlock label={t("prompts.publishedContent")} className="max-h-80">
            {prompt.published_content || <span className="text-muted">{t("prompts.noPublished")}</span>}
          </ReadingBlock>
        </div>
      </details>
    </section>
  );
}
