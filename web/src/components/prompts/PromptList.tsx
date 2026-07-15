import type { ManagedPrompt } from "../../api/prompts";
import { useT } from "../../i18n";
import { groupPromptsByCategory, promptCategoryMeta } from "./promptCategories";

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
  const groups = groupPromptsByCategory(prompts);

  return (
    <aside
      aria-label={t("prompts.indexLabel")}
      className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-card"
    >
      <div className="border-b border-line px-3 py-2.5 text-xs text-muted">
        {t("prompts.promptCount", { n: prompts.length })}
      </div>
      <div
        data-scroll-region="prompt-index"
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain"
      >
        {prompts.length === 0 && <div className="p-4 text-sm text-muted">{t("prompts.empty")}</div>}
        {groups.map((group, groupIndex) => {
          const metadata = promptCategoryMeta(group.category);
          const label = metadata ? t(metadata.labelKey) : group.category;
          const headingId = `prompt-category-${groupIndex}-heading`;
          return (
            <section key={group.category} aria-labelledby={headingId} className="pb-2">
              <div className="sticky top-0 z-10 border-b border-line/70 bg-surface/95 px-3 py-2 backdrop-blur">
                <div className="flex items-center gap-2">
                  <h2 id={headingId} className="text-xs font-semibold text-ink-soft">
                    {label}
                  </h2>
                  <span
                    aria-label={t("prompts.categorySize", { n: group.prompts.length })}
                    className="ml-auto rounded-full bg-well px-1.5 py-0.5 font-mono text-[9px] text-muted"
                  >
                    {group.prompts.length}
                  </span>
                </div>
                {metadata && (
                  <p className="mt-0.5 text-[10px] leading-relaxed text-muted">
                    {t(metadata.descriptionKey)}
                  </p>
                )}
              </div>
              <div className="p-1.5 pb-0">
                {group.prompts.map((prompt) => {
                  const selected = prompt.key === selectedKey;
                  const hasStatus = !prompt.editable || prompt.validation_errors.length > 0;
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
                      {hasStatus && (
                        <span className="mt-1.5 flex items-center gap-2 text-[10px] text-muted">
                          {!prompt.editable && <span>{t("prompts.readOnly")}</span>}
                          {prompt.validation_errors.length > 0 && (
                            <span className="ml-auto text-status-fail-fg">
                              {t("prompts.validation")} {prompt.validation_errors.length}
                            </span>
                          )}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </section>
          );
        })}
      </div>
    </aside>
  );
}
