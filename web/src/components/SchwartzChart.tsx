import { useState } from "react";

import type {
  SchwartzAxis,
  SchwartzStance,
  SchwartzStatus,
  SchwartzValueKey,
  TraitDim,
} from "../api/client";
import { useT } from "../i18n";
import type { Key } from "../i18n/dict";
import { Card } from "./ui/Card";
import {
  circumplexLabelPoint,
  circumplexPoint,
  formatPriority,
  relatedValues,
  schwartzProfile,
  schwartzValues,
  summarizeValues,
  type SchwartzValueView,
} from "./schwartz/model";

const VALUE_LABELS: Record<SchwartzValueKey, Key> = {
  self_direction: "schwartz.value.self_direction",
  stimulation: "schwartz.value.stimulation",
  hedonism: "schwartz.value.hedonism",
  achievement: "schwartz.value.achievement",
  power: "schwartz.value.power",
  security: "schwartz.value.security",
  conformity: "schwartz.value.conformity",
  tradition: "schwartz.value.tradition",
  benevolence: "schwartz.value.benevolence",
  universalism: "schwartz.value.universalism",
};

const TIER_LABELS: Record<SchwartzStatus, Key> = {
  core_priority: "schwartz.tier.core_priority",
  higher_priority: "schwartz.tier.higher_priority",
  context_dependent: "schwartz.tier.context_dependent",
  relative_yielding: "schwartz.tier.relative_yielding",
  explicit_opposition: "schwartz.tier.explicit_opposition",
  unobserved: "schwartz.tier.unobserved",
};

const STANCE_LABELS: Record<SchwartzStance, Key> = {
  support: "schwartz.stance.support",
  oppose: "schwartz.stance.oppose",
  yielding: "schwartz.stance.yielding",
  mixed: "schwartz.stance.mixed",
  unobserved: "schwartz.stance.unobserved",
};

const BASIS_LABELS: Record<string, Key> = {
  costly_choice: "schwartz.basis.costly_choice",
  tradeoff: "schwartz.basis.tradeoff",
  repeated_behavior: "schwartz.basis.repeated_behavior",
  self_statement: "schwartz.basis.self_statement",
  aspiration: "schwartz.basis.aspiration",
  emotion: "schwartz.basis.emotion",
  legacy: "schwartz.basis.legacy",
};

const AXIS_LABELS: Record<SchwartzAxis["left"] | SchwartzAxis["right"], Key> = {
  openness_to_change: "schwartz.axis.openness",
  conservation: "schwartz.axis.conservation",
  self_transcendence: "schwartz.axis.transcendence",
  self_enhancement: "schwartz.axis.enhancement",
};

const valueColor = (value: SchwartzValueView) => {
  if (value.priority === null) return "#706659";
  if (value.explicit_opposition) return "#D98C78";
  return value.priority >= 0 ? "#D0663F" : "#8FB1C2";
};

export function SchwartzChart({ dim }: { dim: TraitDim }) {
  const { t } = useT();
  const profile = schwartzProfile(dim);
  const values = schwartzValues(dim);
  const [selectedKey, setSelectedKey] = useState<SchwartzValueKey>(
    values.find((value) => value.priority !== null)?.key ?? values[0].key,
  );
  const selected = values.find((value) => value.key === selectedKey) ?? values[0];
  const summary = summarizeValues(values);

  return (
    <Card className="p-4 sm:col-span-2">
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="font-serif text-[17px] leading-tight text-ink">{t("schwartz.title")}</div>
        <div className="text-[10px] uppercase tracking-[0.08em] text-muted">
          {t("schwartz.coverage", {
            assessed: profile.coverage.assessed,
            total: profile.coverage.total,
            evidence: profile.coverage.evidence_count,
          })}
        </div>
      </header>
      <p className="mt-1 text-[11px] leading-relaxed text-muted">{t("schwartz.scaleHint")}</p>
      {profile.calibration !== "conversation_evidence" && (
        <p className="mt-2 rounded-md border border-status-warn-fg/20 bg-status-warn-bg px-2.5 py-2 text-[11px] leading-relaxed text-status-warn-fg">
          {t("schwartz.legacyBridge")}
        </p>
      )}

      <div className="mt-3 grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(15rem,0.75fr)]">
        <Circumplex
          values={values}
          selected={selectedKey}
          onSelect={setSelectedKey}
          label={(key) => t(VALUE_LABELS[key])}
          ariaLabel={t("schwartz.circumplexLabel")}
          meanLabel={t("schwartz.meanRing")}
          unobservedLabel={t("schwartz.notEnough")}
        />
        <ValueDetail value={selected} label={(key) => t(VALUE_LABELS[key])} />
      </div>

      <div className="mt-4 border-t border-line pt-3">
        <div className="mb-2 text-[10px] uppercase tracking-[0.1em] text-muted">
          {t("schwartz.axesTitle")}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {profile.axes.map((axis) => <TensionAxis key={axis.key} axis={axis} />)}
        </div>
      </div>

      <div className="mt-4 grid gap-2.5 border-t border-line pt-3 sm:grid-cols-3">
        <ValueGroup title={t("schwartz.coreTitle")} keys={summary.core} />
        <ValueGroup title={t("schwartz.tradeoffsTitle")} keys={summary.tradeoffs} />
        <ValueGroup title={t("schwartz.unobservedTitle")} keys={summary.unobserved} />
      </div>
    </Card>
  );
}

function Circumplex({
  values,
  selected,
  onSelect,
  label,
  ariaLabel,
  meanLabel,
  unobservedLabel,
}: {
  values: SchwartzValueView[];
  selected: SchwartzValueKey;
  onSelect: (key: SchwartzValueKey) => void;
  label: (key: SchwartzValueKey) => string;
  ariaLabel: string;
  meanLabel: string;
  unobservedLabel: string;
}) {
  return (
    <svg viewBox="0 0 360 332" role="img" aria-label={ariaLabel} className="mx-auto w-full max-w-[31rem]">
      <circle cx="180" cy="166" r="120" fill="#110D09" stroke="#281F16" />
      <circle cx="180" cy="166" r="72" fill="none" stroke="#55483A" strokeDasharray="3 4" />
      <text x="180" y="162" textAnchor="middle" fill="#897E6F" fontSize="9">0</text>
      <text x="180" y="176" textAnchor="middle" fill="#706659" fontSize="8">{meanLabel}</text>
      {values.map((value, index) => {
        const meanPoint = circumplexPoint(index, 0);
        const point = circumplexPoint(index, value.priority ?? 0);
        const labelPoint = circumplexLabelPoint(index);
        const color = valueColor(value);
        const opacity = value.priority === null ? 0.45 : 0.35 + value.confidence * 0.65;
        const isSelected = value.key === selected;
        return (
          <g
            key={value.key}
            role="button"
            tabIndex={0}
            aria-label={`${label(value.key)} · ${value.priority === null ? unobservedLabel : formatPriority(value.priority)}`}
            onClick={() => onSelect(value.key)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") onSelect(value.key);
            }}
            className="cursor-pointer outline-none"
          >
            {value.priority !== null && (
              <line
                x1={meanPoint.x} y1={meanPoint.y} x2={point.x} y2={point.y}
                stroke={color} strokeWidth={5} strokeLinecap="round" opacity={opacity * 0.65}
              />
            )}
            {value.activation >= 0.35 && (
              <circle
                cx={point.x} cy={point.y} r={9 + value.activation * 3}
                fill="none" stroke="#D9B36A" strokeWidth="1.5" opacity={value.activation}
              />
            )}
            <circle
              cx={point.x} cy={point.y} r={isSelected ? 5.5 : 4}
              fill={value.priority === null ? "#18120C" : color}
              stroke={isSelected ? "#EFE6D7" : color}
              strokeWidth={isSelected ? 2 : 1.25}
              strokeDasharray={value.priority === null ? "2 2" : undefined}
              opacity={opacity}
            />
            {value.explicit_opposition && (
              <path
                d={`M ${point.x - 4} ${point.y - 4} L ${point.x + 4} ${point.y + 4} M ${point.x + 4} ${point.y - 4} L ${point.x - 4} ${point.y + 4}`}
                stroke="#F0B2A0" strokeWidth="1.5"
              />
            )}
            <text
              x={labelPoint.x} y={labelPoint.y}
              textAnchor="middle" dominantBaseline="middle"
              fill={isSelected ? "#EFE6D7" : value.priority === null ? "#706659" : "#C4B8A6"}
              fontSize="9.5" fontWeight={isSelected ? 600 : 400}
            >
              {label(value.key)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function ValueDetail({ value, label }: {
  value: SchwartzValueView;
  label: (key: SchwartzValueKey) => string;
}) {
  const { t } = useT();
  const related = relatedValues(value.key);
  const interval = value.interval
    ? `${formatPriority(value.interval[0])} … ${formatPriority(value.interval[1])}`
    : "—";
  return (
    <aside className="rounded-lg border border-line bg-well p-3.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-serif text-base text-ink">{label(value.key)}</div>
          <div className="mt-0.5 text-[10px] uppercase tracking-[0.08em] text-muted">
            {t(TIER_LABELS[value.status])}
          </div>
        </div>
        <div className="font-mono text-lg tabular-nums text-gold">{formatPriority(value.priority)}</div>
      </div>

      {value.priority === null ? (
        <p className="mt-4 text-xs leading-relaxed text-muted">{t("schwartz.notEnough")}</p>
      ) : (
        <dl className="mt-4 grid grid-cols-[1fr_auto] gap-x-3 gap-y-2 text-[11px]">
          <dt className="text-muted">{t("schwartz.priority")}</dt>
          <dd className="text-right tabular-nums text-ink-soft">{formatPriority(value.priority)}</dd>
          <dt className="text-muted">{t("schwartz.interval")}</dt>
          <dd className="text-right tabular-nums text-ink-soft">{interval}</dd>
          <dt className="text-muted">{t("schwartz.confidence")}</dt>
          <dd className="text-right tabular-nums text-ink-soft">{Math.round(value.confidence * 100)}%</dd>
          <dt className="text-muted">{t("schwartz.stance")}</dt>
          <dd className="text-right text-ink-soft">{t(STANCE_LABELS[value.stance])}</dd>
          <dt className="text-muted">{t("schwartz.evidenceCount")}</dt>
          <dd className="text-right tabular-nums text-ink-soft">{value.evidence_count}</dd>
          <dt className="text-muted">{t("schwartz.effectiveEvidence")}</dt>
          <dd className="text-right tabular-nums text-ink-soft">{value.effective_evidence.toFixed(2)}</dd>
          <dt className="text-muted">{t("schwartz.activation")}</dt>
          <dd className="text-right tabular-nums text-ink-soft">{Math.round(value.activation * 100)}%</dd>
        </dl>
      )}

      <div className="mt-4">
        <div className="text-[10px] uppercase tracking-[0.08em] text-muted">{t("schwartz.recentEvidence")}</div>
        {value.latest_evidence.length ? (
          <ul className="mt-1.5 space-y-1.5">
            {value.latest_evidence.map((evidence, index) => (
              <li key={`${evidence.quote}-${index}`} className="border-l border-gold/35 pl-2 text-[11px] leading-relaxed text-ink-soft">
                <q>{evidence.quote}</q>
                <div className="mt-0.5 text-[9px] text-muted">
                  {BASIS_LABELS[evidence.basis] ? t(BASIS_LABELS[evidence.basis]) : evidence.basis}
                  {evidence.start_turn !== null && evidence.end_turn !== null
                    ? ` · ${t("schwartz.turnSpan", { start: evidence.start_turn, end: evidence.end_turn })}`
                    : ""}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1.5 text-[11px] text-muted">{t("schwartz.noEvidence")}</p>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 border-t border-line pt-3 text-[10px]">
        <div>
          <div className="text-muted">{t("schwartz.neighbors")}</div>
          <div className="mt-0.5 text-ink-soft">{related.neighbors.map(label).join(" · ")}</div>
        </div>
        <div>
          <div className="text-muted">{t("schwartz.acrossCircle")}</div>
          <div className="mt-0.5 text-ink-soft">{label(related.opposite)}</div>
        </div>
      </div>
    </aside>
  );
}

function TensionAxis({ axis }: { axis: SchwartzAxis }) {
  const { t } = useT();
  const position = axis.score === null ? 50 : (axis.score + 1) * 50;
  return (
    <div className="rounded-md bg-well px-3 py-2.5">
      <div className="flex justify-between gap-3 text-[10px] text-ink-soft">
        <span>{t(AXIS_LABELS[axis.left])}</span>
        <span className="text-right">{t(AXIS_LABELS[axis.right])}</span>
      </div>
      <div className="relative mt-2 h-1 rounded-full bg-line">
        <span className="absolute inset-y-[-2px] left-1/2 w-px bg-muted/60" />
        {axis.score !== null && (
          <span
            className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-surface bg-gold"
            style={{ left: `${position}%`, opacity: 0.45 + axis.confidence * 0.55 }}
          />
        )}
      </div>
    </div>
  );
}

function ValueGroup({ title, keys }: { title: string; keys: SchwartzValueKey[] }) {
  const { t } = useT();
  return (
    <div className="rounded-md bg-well px-3 py-2.5">
      <div className="text-[9px] uppercase tracking-[0.08em] text-muted">{title}</div>
      <div className="mt-1 text-[11px] leading-relaxed text-ink-soft">
        {keys.length ? keys.map((key) => t(VALUE_LABELS[key])).join(" · ") : t("schwartz.none")}
      </div>
    </div>
  );
}
