import { useT } from "../../i18n";
import { Tag } from "../ui/StatusChip";
import type { BackgroundCategory } from "./group";

function humanizeDimension(dimension: string | null): string {
  if (!dimension) return "";
  return dimension
    .split("_")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

export function BackgroundTabs({
  categories,
  active,
  onChange,
}: {
  categories: BackgroundCategory[];
  active: string;
  onChange: (key: string) => void;
}) {
  const { t: tr } = useT();
  const fixedLabels: Record<string, string> = {
    all: tr("traces.bgAll"),
    "trait:ocean": tr("traces.bgOcean"),
    "trait:mbti": tr("traces.bgMbti"),
    "trait:schwartz": tr("traces.bgSchwartz"),
    "trait:regulatory_focus": tr("traces.bgRegulatoryFocus"),
    "trait:unclassified": tr("traces.bgUnclassified"),
    summary: tr("traces.bgSummary"),
    dossier: tr("traces.bgDossier"),
    compact: tr("traces.bgCompact"),
  };

  return (
    <div className="flex-none overflow-hidden border-b border-line bg-canvas/80">
      <div
        role="tablist"
        aria-label={tr("traces.bgTabsLabel")}
        className="flex gap-1 overflow-x-auto px-3 py-2 sm:px-4"
      >
        {categories.map((category) => {
          const selected = category.key === active;
          return (
            <button
              key={category.key}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => onChange(category.key)}
              className={`flex min-h-8 flex-none items-center gap-1.5 whitespace-nowrap rounded-md border px-2.5 text-xs transition-colors ${
                selected
                  ? "border-accent/35 bg-accent/15 text-accent"
                  : "border-line bg-surface text-muted hover:bg-white/5 hover:text-ink-soft"
              }`}
            >
              <span>{fixedLabels[category.key] ?? humanizeDimension(category.dimension)}</span>
              <span className={`font-mono text-[10px] ${selected ? "text-accent" : "text-muted"}`}>
                {category.count}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function DimensionBadge({ dimension }: { dimension: string | null }) {
  const { t: tr } = useT();
  const labels: Record<string, string> = {
    ocean: tr("traces.bgOcean"),
    mbti: tr("traces.bgMbti"),
    schwartz: tr("traces.bgSchwartz"),
    regulatory_focus: tr("traces.bgRegulatoryFocus"),
  };
  return <Tag>{dimension ? labels[dimension] ?? humanizeDimension(dimension) : tr("traces.bgUnclassified")}</Tag>;
}
