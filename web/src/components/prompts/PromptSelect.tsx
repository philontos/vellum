import type { ManagedPrompt } from "../../api/prompts";
import { useT } from "../../i18n";
import { groupPromptsByCategory, promptCategoryMeta } from "./promptCategories";

export function PromptSelect({
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
    <label className="block">
      <span className="mb-1 block text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
        {t("prompts.choosePrompt")}
      </span>
      <select
        aria-label={t("prompts.choosePrompt")}
        value={selectedKey}
        disabled={disabled}
        onChange={(event) => onSelect(event.target.value)}
        className="min-h-11 w-full rounded-lg border border-line bg-surface px-3 text-base text-ink-soft focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:opacity-60"
      >
        {groups.map((group) => {
          const metadata = promptCategoryMeta(group.category);
          return (
            <optgroup
              key={group.category}
              label={metadata ? t(metadata.labelKey) : group.category}
            >
              {group.prompts.map((prompt) => {
                const statuses = [
                  prompt.is_modified ? t("prompts.modified") : "",
                  !prompt.editable ? t("prompts.readOnly") : "",
                  prompt.validation_errors.length > 0
                    ? `${t("prompts.validation")} ${prompt.validation_errors.length}`
                    : "",
                ].filter(Boolean);
                return (
                  <option key={prompt.key} value={prompt.key}>
                    {prompt.name} · {prompt.key}
                    {statuses.length > 0 ? ` · ${statuses.join(" · ")}` : ""}
                  </option>
                );
              })}
            </optgroup>
          );
        })}
      </select>
    </label>
  );
}
