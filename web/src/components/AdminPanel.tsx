import { useState } from "react";

import type { AuthUser } from "../auth/client";
import { useT } from "../i18n";
import { EvalPanel } from "./EvalPanel";
import { ModelCandidatesPanel } from "./ModelCandidatesPanel";
import { ProbePanel } from "./ProbePanel";
import { PromptsPanel } from "./PromptsPanel";
import { TracesPanel } from "./TracesPanel";

export type AdminSection = "prompts" | "models" | "traces" | "probe" | "evals";

const OWNER_SECTIONS: AdminSection[] = [
  "prompts", "models", "traces", "probe", "evals",
];
const MEMBER_SECTIONS: AdminSection[] = ["traces", "probe"];

export function adminSectionsForUser(user: AuthUser | null): AdminSection[] {
  return user?.role === "member" ? [...MEMBER_SECTIONS] : [...OWNER_SECTIONS];
}

export function allowAdminSectionChange(
  current: AdminSection,
  next: AdminSection,
  promptDirty: boolean,
  confirmDiscard: () => boolean,
): boolean {
  if (next === current) return true;
  return current !== "prompts" || !promptDirty || confirmDiscard();
}

export function AdminPanel({
  user,
  promptDirty,
  onPromptDirtyChange,
}: {
  user: AuthUser | null;
  promptDirty: boolean;
  onPromptDirtyChange: (dirty: boolean) => void;
}) {
  const { t } = useT();
  const sections = adminSectionsForUser(user);
  const [selected, setSelected] = useState<AdminSection>(() => sections[0]);
  const active = sections.includes(selected) ? selected : sections[0];

  function select(next: AdminSection) {
    if (next === active) return;
    if (!allowAdminSectionChange(
      active,
      next,
      promptDirty,
      () => window.confirm(t("prompts.discardConfirm")),
    )) return;
    if (active === "prompts") onPromptDirtyChange(false);
    setSelected(next);
  }

  const labels: Record<AdminSection, string> = {
    prompts: t("nav.prompts"),
    models: t("nav.models"),
    traces: t("nav.traces"),
    probe: t("nav.probe"),
    evals: t("nav.evals"),
  };

  return (
    <div className="hidden h-full min-h-0 flex-col overflow-hidden md:flex">
      <header className="flex flex-none items-center gap-4 border-b border-line bg-canvas/95 px-4 py-2.5">
        <h1 className="flex-none font-serif text-xl text-ink">{t("nav.admin")}</h1>
        <div
          role="tablist"
          aria-label={t("admin.tabsLabel")}
          className="flex min-w-0 gap-1 overflow-x-auto rounded-lg border border-line bg-well p-1"
        >
          {sections.map((section) => {
            const selectedTab = section === active;
            return (
              <button
                key={section}
                id={`admin-tab-${section}`}
                type="button"
                role="tab"
                aria-selected={selectedTab}
                aria-controls={`admin-panel-${section}`}
                tabIndex={selectedTab ? 0 : -1}
                onClick={() => select(section)}
                className={
                  "flex min-h-9 flex-none items-center gap-2 whitespace-nowrap rounded-md px-3 text-sm transition-colors " +
                  (selectedTab
                    ? "bg-surface text-ink shadow-card"
                    : "text-muted hover:bg-white/5 hover:text-ink-soft")
                }
              >
                {labels[section]}
                {section === "prompts" && promptDirty && (
                  <span className="h-1.5 w-1.5 rounded-full bg-status-warn-fg" aria-hidden />
                )}
              </button>
            );
          })}
        </div>
      </header>

      <div
        id={`admin-panel-${active}`}
        role="tabpanel"
        aria-labelledby={`admin-tab-${active}`}
        className="min-h-0 flex-1 overflow-hidden"
      >
        {active === "prompts" && <PromptsPanel onDirtyChange={onPromptDirtyChange} />}
        {active === "models" && <ModelCandidatesPanel />}
        {active === "traces" && <TracesPanel />}
        {active === "probe" && <ProbePanel />}
        {active === "evals" && <EvalPanel />}
      </div>
    </div>
  );
}
