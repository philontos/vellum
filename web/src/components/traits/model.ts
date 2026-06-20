import type { TraitDim } from "../../api/client";

/** One renderable sub-dimension row: its current score, optional poles (=> bipolar),
 * the score series over time, and the since-first delta (null when too short). */
export type TraitRow = {
  key: string;
  label: string;
  score: number;
  poles?: [string, string];
  history: number[];
  delta: number | null;
};

/** Ordered rows for a dimension. Uses meta order + labels + poles when present;
 * otherwise falls back to content_json keys (unipolar). Sub-dimensions without a
 * numeric score yet are dropped. Sorted by score desc when meta.sort_by_score. */
export function traitRows(dim: TraitDim): TraitRow[] {
  const metaSubs = dim.meta?.sub_dimensions;
  const specs = metaSubs && metaSubs.length
    ? metaSubs.map((s) => ({ key: s.key, label: s.name, poles: s.poles }))
    : Object.keys(dim.content_json).map((k) => ({ key: k, label: k, poles: undefined as [string, string] | undefined }));

  const rows: TraitRow[] = [];
  for (const spec of specs) {
    const score = dim.content_json[spec.key]?.score;
    if (typeof score !== "number") continue;
    const history = dim.history
      .map((h) => h.content_json[spec.key]?.score)
      .filter((s): s is number => typeof s === "number");
    const delta = history.length >= 2 ? history[history.length - 1] - history[0] : null;
    rows.push({ key: spec.key, label: spec.label, score, poles: spec.poles, history, delta });
  }
  if (dim.meta?.sort_by_score) rows.sort((a, b) => b.score - a.score);
  return rows;
}

/** For a bipolar score (0..100), which pole it leans to. >50 → high pole (@100),
 * <50 → low pole (@0), exactly 50 → balanced. */
export function leaning(score: number, poles: [string, string]): { pole: string; side: "low" | "high" | "mid" } {
  if (score > 50) return { pole: poles[1], side: "high" };
  if (score < 50) return { pole: poles[0], side: "low" };
  return { pole: "", side: "mid" };
}

/** SVG polyline points for a sparkline, autoscaled to the series (with 2px vertical
 * padding); higher value → lower y. Flat midline for constant/single series, "" for none. */
export function sparkline(values: number[], w: number, h: number): string {
  if (values.length === 0) return "";
  if (values.length === 1) return `0,${h / 2} ${w},${h / 2}`;
  const min = Math.min(...values), max = Math.max(...values), range = max - min;
  const pad = 2, usable = h - 2 * pad, n = values.length;
  return values
    .map((v, i) => {
      const x = (i * w) / (n - 1);
      const y = range === 0 ? h / 2 : pad + (1 - (v - min) / range) * usable;
      return `${x},${y}`;
    })
    .join(" ");
}
