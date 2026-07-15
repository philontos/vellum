import { useT } from "../../i18n";

export type PromptWorkspaceTab = "manage" | "history";

const TABS: PromptWorkspaceTab[] = ["manage", "history"];

export function PromptWorkspaceTabs({
  active,
  dirty,
  releaseCount,
  onChange,
}: {
  active: PromptWorkspaceTab;
  dirty: boolean;
  releaseCount: number;
  onChange: (tab: PromptWorkspaceTab) => void;
}) {
  const { t } = useT();
  const labels: Record<PromptWorkspaceTab, string> = {
    manage: t("prompts.workspaceTabManage"),
    history: t("prompts.workspaceTabHistory"),
  };

  function move(from: number, delta: number) {
    const next = TABS[(from + delta + TABS.length) % TABS.length];
    focus(next);
  }

  function focus(next: PromptWorkspaceTab) {
    onChange(next);
    requestAnimationFrame(() => {
      document.getElementById(`prompt-workspace-tab-${next}`)?.focus();
    });
  }

  return (
    <div className="flex-none border-b border-line bg-surface/40 px-4 sm:px-5">
      <div
        role="tablist"
        aria-label={t("prompts.workspaceTabsLabel")}
        className="mx-auto flex w-full max-w-7xl gap-5"
      >
        {TABS.map((tab, index) => {
          const selected = active === tab;
          return (
            <button
              type="button"
              id={`prompt-workspace-tab-${tab}`}
              role="tab"
              aria-selected={selected}
              aria-controls={`prompt-workspace-panel-${tab}`}
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
                } else if (event.key === "Home") {
                  event.preventDefault();
                  focus(TABS[0]);
                } else if (event.key === "End") {
                  event.preventDefault();
                  focus(TABS[TABS.length - 1]);
                }
              }}
              className={
                "min-h-11 border-b-2 px-0.5 text-sm transition-colors " +
                (selected
                  ? "border-accent text-ink"
                  : "border-transparent text-muted hover:text-ink-soft")
              }
            >
              <span className="inline-flex items-center gap-2">
                {labels[tab]}
                {tab === "manage" && dirty && (
                  <span
                    aria-label={t("prompts.unsaved")}
                    className="h-1.5 w-1.5 rounded-full bg-status-warn-fg"
                  />
                )}
                {tab === "history" && (
                  <span className="rounded-full bg-well px-1.5 py-0.5 font-mono text-[9px] text-muted">
                    {releaseCount}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
