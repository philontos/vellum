import { useT } from "../../i18n";

export type PromptEditorTab = "edit" | "guide";

const TABS: PromptEditorTab[] = ["edit", "guide"];

export function PromptEditorTabs({
  active,
  dirty,
  onChange,
}: {
  active: PromptEditorTab;
  dirty: boolean;
  onChange: (tab: PromptEditorTab) => void;
}) {
  const { t } = useT();
  const labels: Record<PromptEditorTab, string> = {
    edit: t("prompts.tabEdit"),
    guide: t("prompts.tabGuide"),
  };

  function move(from: number, delta: number) {
    const next = TABS[(from + delta + TABS.length) % TABS.length];
    onChange(next);
    requestAnimationFrame(() => document.getElementById(`prompt-tab-${next}`)?.focus());
  }

  return (
    <div
      role="tablist"
      aria-label={t("prompts.tabsLabel")}
      className="mt-5 flex rounded-xl border border-line bg-well p-1"
    >
      {TABS.map((tab, index) => {
        const selected = active === tab;
        return (
          <button
            type="button"
            id={`prompt-tab-${tab}`}
            role="tab"
            aria-selected={selected}
            aria-controls={`prompt-panel-${tab}`}
            tabIndex={selected ? 0 : -1}
            key={tab}
            onClick={() => onChange(tab)}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight") {
                event.preventDefault();
                move(index, 1);
              } else if (event.key === "ArrowLeft") {
                event.preventDefault();
                move(index, -1);
              }
            }}
            className={
              "min-h-10 min-w-0 flex-1 rounded-lg px-3 text-sm transition-colors " +
              (selected
                ? "bg-surface text-ink shadow-card"
                : "text-muted hover:text-ink-soft")
            }
          >
            <span className="inline-flex items-center gap-1.5">
              {labels[tab]}
              {tab === "edit" && dirty && (
                <span
                  aria-label={t("prompts.unsaved")}
                  className="h-1.5 w-1.5 rounded-full bg-status-warn-fg"
                />
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
