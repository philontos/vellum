import type { ManagedPrompt } from "../../api/prompts";
import { useT } from "../../i18n";

export function PromptList({
  prompts,
  selectedKey,
  disabled,
  onSelect,
}: {
  prompts: ManagedPrompt[];
  selectedKey: string;
  disabled: boolean;
  onSelect: (key: string) => void;
}) {
  const { t } = useT();

  return (
    <aside className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="border-b border-line px-3 py-2.5 text-xs text-muted">
        {t("prompts.promptCount", { n: prompts.length })}
      </div>
      <div className="max-h-[34rem] overflow-y-auto p-1.5">
        {prompts.length === 0 && <div className="p-4 text-sm text-muted">{t("prompts.empty")}</div>}
        {prompts.map((prompt) => {
          const selected = prompt.key === selectedKey;
          return (
            <button
              type="button"
              key={prompt.key}
              disabled={disabled}
              onClick={() => onSelect(prompt.key)}
              aria-current={selected ? "true" : undefined}
              className={
                "mb-1 w-full rounded-lg border-l-2 px-3 py-2.5 text-left transition-colors disabled:cursor-wait " +
                (selected
                  ? "border-accent bg-accent/10 text-ink"
                  : "border-transparent text-ink-soft hover:bg-white/5")
              }
            >
              <span className="flex items-start gap-2">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{prompt.name}</span>
                  <span className="mt-0.5 block truncate font-mono text-[10px] text-muted">
                    {prompt.key}
                  </span>
                </span>
                {prompt.is_modified && (
                  <span className="mt-0.5 flex-none rounded-full bg-status-warn-bg px-1.5 py-0.5 text-[9px] text-status-warn-fg">
                    {t("prompts.modified")}
                  </span>
                )}
              </span>
              <span className="mt-1.5 flex items-center gap-2 text-[10px] text-muted">
                <span>{prompt.category}</span>
                {!prompt.editable && <span>· {t("prompts.readOnly")}</span>}
                {prompt.validation_errors.length > 0 && (
                  <span className="ml-auto text-status-fail-fg">
                    {t("prompts.validation")} {prompt.validation_errors.length}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
