import { useT } from "../../i18n";

export type ModelSection = "dossier" | "evidence" | "facts" | "traits";

const SECTIONS: ModelSection[] = ["dossier", "evidence", "facts", "traits"];

export function ModelTabs({
  active,
  onChange,
}: {
  active: ModelSection;
  onChange: (section: ModelSection) => void;
}) {
  const { t } = useT();
  const labels: Record<ModelSection, string> = {
    dossier: t("model.tabDossier"),
    evidence: t("model.tabEvidence"),
    facts: t("model.tabFacts"),
    traits: t("model.tabTraits"),
  };

  function move(from: number, delta: number) {
    const next = SECTIONS[(from + delta + SECTIONS.length) % SECTIONS.length];
    onChange(next);
    requestAnimationFrame(() => document.getElementById(`model-tab-${next}`)?.focus());
  }

  return (
    <div className="sticky top-0 z-20 border-b border-line bg-canvas/95 px-4 py-2.5 backdrop-blur lg:px-8 lg:py-3">
      <div
        role="tablist"
        aria-label={t("model.tabsLabel")}
        className="mx-auto flex w-full max-w-lg rounded-xl border border-line bg-well p-1"
      >
        {SECTIONS.map((section, index) => {
          const selected = active === section;
          return (
            <button
              type="button"
              id={`model-tab-${section}`}
              role="tab"
              aria-selected={selected}
              aria-controls={`model-panel-${section}`}
              tabIndex={selected ? 0 : -1}
              key={section}
              onClick={() => onChange(section)}
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
                "min-h-10 min-w-0 flex-1 rounded-lg px-2 text-sm transition-colors " +
                (selected
                  ? "bg-surface text-ink shadow-card"
                  : "text-muted hover:text-ink-soft")
              }
            >
              <span className="block truncate">{labels[section]}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
