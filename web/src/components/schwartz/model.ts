import type {
  SchwartzAxis,
  SchwartzProfile,
  SchwartzStatus,
  SchwartzValue,
  SchwartzValueKey,
  TraitDim,
} from "../../api/client";

export const SCHWARTZ_KEYS: SchwartzValueKey[] = [
  "self_direction", "stimulation", "hedonism", "achievement", "power",
  "security", "conformity", "tradition", "benevolence", "universalism",
];

export type SchwartzValueView = SchwartzValue & { key: SchwartzValueKey };

const emptyValue = (): SchwartzValue => ({
  priority: null,
  interval: null,
  confidence: 0,
  stance: "unobserved",
  explicit_opposition: false,
  evidence_count: 0,
  effective_evidence: 0,
  activation: 0,
  status: "unobserved",
  evidence: null,
  latest_evidence: [],
});

function tier(priority: number | null): SchwartzStatus {
  if (priority === null) return "unobserved";
  if (priority >= 0.25) return "core_priority";
  if (priority >= 0.08) return "higher_priority";
  if (priority <= -0.08) return "relative_yielding";
  return "context_dependent";
}

function mean(values: Array<number | null>): number | null {
  const observed = values.filter((value): value is number => value !== null);
  return observed.length ? observed.reduce((sum, value) => sum + value, 0) / observed.length : null;
}

function axes(values: SchwartzProfile["values"]): SchwartzAxis[] {
  const axis = (
    key: SchwartzAxis["key"], left: SchwartzAxis["left"], right: SchwartzAxis["right"],
    leftKeys: SchwartzValueKey[], rightKeys: SchwartzValueKey[],
  ): SchwartzAxis => {
    const l = mean(leftKeys.map((value) => values[value].priority));
    const r = mean(rightKeys.map((value) => values[value].priority));
    const members = [...leftKeys, ...rightKeys]
      .map((value) => values[value])
      .filter((value) => value.priority !== null);
    return {
      key, left, right,
      score: l === null || r === null ? null : Math.max(-1, Math.min(1, (r - l) / 2)),
      confidence: members.length
        ? members.reduce((sum, value) => sum + value.confidence, 0) / members.length
        : 0,
    };
  };
  return [
    axis(
      "openness_conservation", "openness_to_change", "conservation",
      ["self_direction", "stimulation", "hedonism"],
      ["security", "conformity", "tradition"],
    ),
    axis(
      "transcendence_enhancement", "self_transcendence", "self_enhancement",
      ["universalism", "benevolence"], ["achievement", "power", "hedonism"],
    ),
  ];
}

/** Compatibility view for a server that has not projected its old 0–100 state yet. */
export function legacySchwartzProfile(dim: TraitDim): SchwartzProfile {
  const observedScores = SCHWARTZ_KEYS
    .map((key) => dim.content_json[key]?.score)
    .filter((score): score is number => typeof score === "number");
  const personalMean = observedScores.length
    ? observedScores.reduce((sum, score) => sum + score, 0) / observedScores.length
    : 50;
  const values = {} as SchwartzProfile["values"];
  for (const key of SCHWARTZ_KEYS) {
    const item = dim.content_json[key];
    const score = item?.score;
    if (typeof score !== "number") {
      values[key] = emptyValue();
      continue;
    }
    const priority = Math.max(-1, Math.min(1, (score - personalMean) / 100));
    const confidence = item.confidence ?? 0.25;
    const halfWidth = Math.min(0.5, 0.25 / Math.max(0.25, Math.sqrt(confidence)));
    values[key] = {
      priority,
      interval: [Math.max(-1, priority - halfWidth), Math.min(1, priority + halfWidth)],
      confidence,
      stance: score >= 50 ? "support" : "yielding",
      explicit_opposition: false,
      evidence_count: 1,
      effective_evidence: confidence,
      activation: 0,
      status: tier(priority),
      evidence: item.evidence ?? null,
      latest_evidence: item.evidence ? [{
        quote: item.evidence,
        direction: score >= 50 ? "support" : "sacrifice",
        basis: "legacy",
        counterpart: null,
        start_turn: null,
        end_turn: null,
      }] : [],
    };
  }
  const assessed = observedScores.length;
  return {
    kind: "schwartz_circumplex",
    model_version: "schwartz-v2",
    calibration: "legacy_bridge",
    scale: { minimum: -1, center: 0, maximum: 1, meaning: "within_person_relative_priority" },
    coverage: { assessed, total: SCHWARTZ_KEYS.length, evidence_count: assessed },
    values,
    axes: axes(values),
  };
}

export function schwartzProfile(dim: TraitDim): SchwartzProfile {
  return dim.profile ?? legacySchwartzProfile(dim);
}

export function schwartzValues(dim: TraitDim): SchwartzValueView[] {
  const values = schwartzProfile(dim).values;
  return SCHWARTZ_KEYS.map((key) => ({ key, ...(values[key] ?? emptyValue()) }));
}

const CENTER_X = 180;
const CENTER_Y = 166;
const MEAN_RADIUS = 72;
const PRIORITY_SPAN = 48;

export function circumplexPoint(index: number, priority: number): { x: number; y: number } {
  const angle = (-90 + index * (360 / SCHWARTZ_KEYS.length)) * Math.PI / 180;
  const radius = MEAN_RADIUS + Math.max(-1, Math.min(1, priority)) * PRIORITY_SPAN;
  return {
    x: CENTER_X + Math.cos(angle) * radius,
    y: CENTER_Y + Math.sin(angle) * radius,
  };
}

export function circumplexLabelPoint(index: number): { x: number; y: number } {
  const angle = (-90 + index * (360 / SCHWARTZ_KEYS.length)) * Math.PI / 180;
  const radius = 137;
  return { x: CENTER_X + Math.cos(angle) * radius, y: CENTER_Y + Math.sin(angle) * radius };
}

export function relatedValues(key: SchwartzValueKey): {
  neighbors: [SchwartzValueKey, SchwartzValueKey]; opposite: SchwartzValueKey;
} {
  const index = SCHWARTZ_KEYS.indexOf(key);
  return {
    neighbors: [
      SCHWARTZ_KEYS[(index - 1 + SCHWARTZ_KEYS.length) % SCHWARTZ_KEYS.length],
      SCHWARTZ_KEYS[(index + 1) % SCHWARTZ_KEYS.length],
    ],
    opposite: SCHWARTZ_KEYS[(index + SCHWARTZ_KEYS.length / 2) % SCHWARTZ_KEYS.length],
  };
}

export function summarizeValues(values: SchwartzValueView[]): {
  core: SchwartzValueKey[]; tradeoffs: SchwartzValueKey[]; unobserved: SchwartzValueKey[];
} {
  return {
    core: values
      .filter((value) => value.status === "core_priority" || value.status === "higher_priority")
      .map((value) => value.key),
    tradeoffs: values
      .filter((value) => ["relative_yielding", "explicit_opposition"].includes(value.status))
      .map((value) => value.key),
    unobserved: values.filter((value) => value.priority === null).map((value) => value.key),
  };
}

export function formatPriority(priority: number | null): string {
  if (priority === null) return "—";
  return `${priority >= 0 ? "+" : ""}${priority.toFixed(2)}`;
}
