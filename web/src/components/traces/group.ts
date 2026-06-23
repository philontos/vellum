// Reshape the flat trace list into the two views the panel shows:
//   • Rounds      — chat + the facts it triggered, grouped by their shared turn
//   • Background  — trait/summary/dossier passes, each spanning a turn *range*
// Pure functions (no React) so they can be unit-tested in isolation.
import type { Trace } from "../../api/client";

const ROUND_STAGES = new Set(["chat", "facts"]);
// compact is a periodic whole-board fact compaction (facts.py, every N turns) —
// it covers a turn *range* like the other passes, so it belongs in Background.
const BG_STAGES = new Set(["trait", "summary", "dossier", "compact"]);

/** One conversation round: its chat call plus the facts extraction(s) it triggered. */
export type Round = { turn: number | null; chat: Trace | null; facts: Trace[] };

/** A background pass, annotated with the turn range it actually covered. */
export type Pass = Trace & { from: number | null; to: number | null };

/**
 * Group chat + facts traces by turn into rounds, newest turn first. Legacy
 * chat traces with no turn (recorded before rounds were anchored) fall into a
 * single trailing `turn: null` bucket so they're never lost.
 */
export function groupRounds(traces: Trace[]): Round[] {
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
export function parseSpan(trace: Trace): { from: number | null; to: number | null } {
  if (!trace.params) return { from: null, to: null };
  try {
    const p = JSON.parse(trace.params) as { from?: number; to?: number };
    return { from: p.from ?? null, to: p.to ?? null };
  } catch {
    return { from: null, to: null };
  }
}

/** trait/summary/dossier passes, newest first, each with its covered span. */
export function backgroundPasses(traces: Trace[]): Pass[] {
  return traces
    .filter((tr) => BG_STAGES.has(tr.stage))
    .sort((a, b) => b.id - a.id)
    .map((tr) => ({ ...tr, ...parseSpan(tr) }));
}

/** The last user message inside a chat trace's prompt, for a scannable round title. */
export function userSnippet(chat: Trace | null): string | null {
  if (!chat?.prompt) return null;
  try {
    const msgs = JSON.parse(chat.prompt) as { role?: string; content?: string }[];
    if (!Array.isArray(msgs)) return null;
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i]?.role === "user" && typeof msgs[i].content === "string") {
        return msgs[i].content as string;
      }
    }
    return null;
  } catch {
    return null;
  }
}
