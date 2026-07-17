// Reshape the flat trace list into the two views the panel shows:
//   • Rounds      — chat + the facts it triggered, grouped by their shared turn
//   • Background  — trait/summary/dossier passes, each spanning a turn *range*
// Pure functions (no React) so they can be unit-tested in isolation.
import type { TraceSummary } from "../../api/client";

const ROUND_STAGES = new Set(["chat", "facts"]);
// compact is a periodic whole-board fact compaction (facts.py, every N turns) —
// it covers a turn *range* like the other passes, so it belongs in Background.
const BG_STAGES = new Set(["trait", "summary", "dossier", "compact"]);
const KNOWN_TRAIT_DIMENSIONS = ["ocean", "mbti", "schwartz", "regulatory_focus"] as const;

/** One conversation round: its chat call plus the facts extraction(s) it triggered. */
export type Round = { turn: number | null; chat: TraceSummary | null; facts: TraceSummary[] };

/** A background pass, annotated with the turn range it actually covered. */
export type Pass = TraceSummary & { from: number | null; to: number | null };

/** One stable filter tab inside Background. Future dimensions are appended
 * dynamically; legacy rows that cannot be identified remain discoverable. */
export type BackgroundCategory = {
  key: string;
  count: number;
  stage: "all" | "trait" | "summary" | "dossier" | "compact";
  dimension: string | null;
};

/**
 * Group chat + facts traces by turn into rounds, newest turn first. Legacy
 * chat traces with no turn (recorded before rounds were anchored) fall into a
 * single trailing `turn: null` bucket so they're never lost.
 */
export function groupRounds(traces: TraceSummary[]): Round[] {
  const byTurn = new Map<number | null, Round>();
  for (const tr of traces) {
    if (!ROUND_STAGES.has(tr.stage)) continue;
    let round = byTurn.get(tr.turn);
    if (!round) {
      round = { turn: tr.turn, chat: null, facts: [] };
      byTurn.set(tr.turn, round);
    }
    if (tr.stage === "chat") round.chat = tr;
    else round.facts.push(tr);
  }
  return [...byTurn.values()].sort((a, b) => {
    if (a.turn === null) return 1; // ungrouped sinks to the bottom
    if (b.turn === null) return -1;
    return b.turn - a.turn; // newest round first
  });
}

/** The covered turn span of a pass, read from its params JSON. */
export function parseSpan(trace: TraceSummary): { from: number | null; to: number | null } {
  if (!trace.params) return { from: null, to: null };
  try {
    const p = JSON.parse(trace.params) as { from?: number; to?: number };
    return { from: p.from ?? null, to: p.to ?? null };
  } catch {
    return { from: null, to: null };
  }
}

/** trait/summary/dossier passes, newest first, each with its covered span. */
export function backgroundPasses(traces: TraceSummary[]): Pass[] {
  return traces
    .filter((tr) => BG_STAGES.has(tr.stage))
    .sort((a, b) => b.id - a.id)
    .map((tr) => ({ ...tr, ...parseSpan(tr) }));
}

export function filterBackgroundPasses(passes: Pass[], key: string): Pass[] {
  if (key === "all") return passes;
  if (key.startsWith("trait:")) {
    const dimension = key.slice("trait:".length);
    return passes.filter((pass) => (
      pass.stage === "trait"
      && (dimension === "unclassified" ? pass.dimension === null : pass.dimension === dimension)
    ));
  }
  return passes.filter((pass) => pass.stage === key);
}

export function backgroundCategories(passes: Pass[]): BackgroundCategory[] {
  const known = new Set<string>(KNOWN_TRAIT_DIMENSIONS);
  const extraDimensions = [...new Set(
    passes
      .filter((pass) => pass.stage === "trait" && pass.dimension && !known.has(pass.dimension))
      .map((pass) => pass.dimension as string),
  )].sort((a, b) => a.localeCompare(b));
  const dimensions = [...KNOWN_TRAIT_DIMENSIONS, ...extraDimensions];

  const categories: BackgroundCategory[] = [
    { key: "all", count: passes.length, stage: "all", dimension: null },
    ...dimensions.map((dimension) => ({
      key: `trait:${dimension}`,
      count: filterBackgroundPasses(passes, `trait:${dimension}`).length,
      stage: "trait" as const,
      dimension,
    })),
  ];

  if (passes.some((pass) => pass.stage === "trait" && pass.dimension === null)) {
    categories.push({
      key: "trait:unclassified",
      count: filterBackgroundPasses(passes, "trait:unclassified").length,
      stage: "trait",
      dimension: null,
    });
  }

  for (const stage of ["summary", "dossier", "compact"] as const) {
    categories.push({
      key: stage,
      count: filterBackgroundPasses(passes, stage).length,
      stage,
      dimension: null,
    });
  }
  return categories;
}

/** The last user message inside a chat trace's prompt, for a scannable round title. */
export function userSnippet(chat: TraceSummary | null): string | null {
  return chat?.snippet ?? null;
}
