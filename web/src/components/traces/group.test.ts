import { describe, it, expect } from "vitest";
import type { TraceSummary } from "../../api/client";
import {
  backgroundCategories,
  backgroundPasses,
  filterBackgroundPasses,
  groupRounds,
  parseSpan,
  userSnippet,
} from "./group";

// Minimal summary factory — only the fields a test cares about; the rest default.
function t(p: Partial<TraceSummary> & { id: number; stage: string }): TraceSummary {
  return {
    turn: null, model: "m", snippet: null, dimension: null,
    prompt_tokens: null, completion_tokens: null, duration_ms: null,
    pinned: 0, note: null, created_at: "2026-06-20 10:00:00", params: null,
    has_reasoning: false, has_tool_calls: false,
    ...p,
  };
}

describe("groupRounds", () => {
  it("groups a round's chat and facts under their shared turn", () => {
    const rounds = groupRounds([
      t({ id: 2, stage: "facts", turn: 1 }),
      t({ id: 1, stage: "chat", turn: 1 }),
    ]);
    expect(rounds).toHaveLength(1);
    expect(rounds[0].turn).toBe(1);
    expect(rounds[0].chat?.id).toBe(1);
    expect(rounds[0].facts.map((f) => f.id)).toEqual([2]);
  });

  it("orders rounds newest-first by turn", () => {
    const rounds = groupRounds([
      t({ id: 1, stage: "chat", turn: 1 }),
      t({ id: 2, stage: "chat", turn: 3 }),
    ]);
    expect(rounds.map((r) => r.turn)).toEqual([3, 1]);
  });

  it("ignores background stages", () => {
    const rounds = groupRounds([
      t({ id: 1, stage: "chat", turn: 1 }),
      t({ id: 2, stage: "trait", turn: 1 }),
      t({ id: 3, stage: "summary", turn: 1 }),
      t({ id: 4, stage: "dossier", turn: 1 }),
      t({ id: 5, stage: "compact", turn: 1 }),
      t({ id: 6, stage: "dossier_evidence", turn: 1 }),
      t({ id: 7, stage: "dossier_render", turn: 1 }),
    ]);
    expect(rounds).toHaveLength(1);
    expect(rounds[0].chat?.id).toBe(1);
    expect(rounds[0].facts).toEqual([]);
  });

  it("collects multiple facts traces of the same round", () => {
    const rounds = groupRounds([
      t({ id: 3, stage: "facts", turn: 2 }),
      t({ id: 2, stage: "facts", turn: 2 }),
      t({ id: 1, stage: "chat", turn: 2 }),
    ]);
    expect(rounds[0].facts.map((f) => f.id)).toEqual([3, 2]);
  });

  it("puts legacy null-turn chat traces in a trailing ungrouped round", () => {
    const rounds = groupRounds([
      t({ id: 1, stage: "chat", turn: null }),
      t({ id: 2, stage: "chat", turn: 2 }),
    ]);
    expect(rounds.map((r) => r.turn)).toEqual([2, null]);
    expect(rounds[1].chat?.id).toBe(1);
  });
});

describe("backgroundPasses", () => {
  it("selects the background stages and parses the covered span", () => {
    const passes = backgroundPasses([
      t({ id: 1, stage: "chat", turn: 1 }),
      t({ id: 2, stage: "facts", turn: 1 }),
      t({ id: 3, stage: "trait", turn: 14, params: JSON.stringify({ from: 8, to: 14 }) }),
      t({ id: 4, stage: "dossier_evidence", turn: 14 }),
      t({ id: 5, stage: "dossier_render", turn: 14 }),
    ]);
    expect(passes).toHaveLength(3);
    const trait = passes.find((pass) => pass.stage === "trait");
    expect(trait?.from).toBe(8);
    expect(trait?.to).toBe(14);
  });

  it("orders passes newest-first by id", () => {
    const passes = backgroundPasses([
      t({ id: 5, stage: "summary" }),
      t({ id: 9, stage: "dossier" }),
      t({ id: 7, stage: "trait" }),
    ]);
    expect(passes.map((p) => p.id)).toEqual([9, 7, 5]);
  });

  it("tolerates missing or malformed params → from/to null", () => {
    const passes = backgroundPasses([
      t({ id: 1, stage: "trait", params: null }),
      t({ id: 2, stage: "summary", params: "not json" }),
    ]);
    expect(passes.every((p) => p.from === null && p.to === null)).toBe(true);
  });

  it("includes compact (whole-board fact compaction) with its covered span", () => {
    const passes = backgroundPasses([
      t({ id: 1, stage: "chat", turn: 20 }),
      t({ id: 2, stage: "facts", turn: 20 }),
      t({ id: 3, stage: "compact", turn: 20, params: JSON.stringify({ from: 1, to: 20 }) }),
    ]);
    expect(passes).toHaveLength(1);
    expect(passes[0].stage).toBe("compact");
    expect(passes[0].from).toBe(1);
    expect(passes[0].to).toBe(20);
  });
});

describe("backgroundCategories", () => {
  const passes = backgroundPasses([
    t({ id: 8, stage: "trait", dimension: "ocean" }),
    t({ id: 7, stage: "trait", dimension: "mbti" }),
    t({ id: 6, stage: "trait", dimension: "ocean" }),
    t({ id: 5, stage: "summary" }),
    t({ id: 4, stage: "dossier" }),
    t({ id: 3, stage: "compact" }),
    t({ id: 2, stage: "dossier_evidence" }),
    t({ id: 1, stage: "dossier_render" }),
  ]);

  it("provides stable tabs with per-category counts", () => {
    const categories = backgroundCategories(passes);

    expect(categories.map((category) => category.key)).toEqual([
      "all",
      "trait:ocean",
      "trait:mbti",
      "trait:schwartz",
      "trait:regulatory_focus",
      "summary",
      "dossier_evidence",
      "dossier_render",
      "compact",
    ]);
    expect(categories.find((category) => category.key === "trait:ocean")?.count).toBe(2);
    expect(categories.find((category) => category.key === "summary")?.count).toBe(1);
    expect(categories.find((category) => category.key === "dossier_evidence")?.count).toBe(1);
    expect(categories.find((category) => category.key === "dossier_render")?.count).toBe(2);
    expect(categories.find((category) => category.key === "trait:schwartz")?.count).toBe(0);
  });

  it("groups legacy dossier traces into the render category", () => {
    expect(filterBackgroundPasses(passes, "dossier_render").map((pass) => pass.stage)).toEqual([
      "dossier",
      "dossier_render",
    ]);
  });

  it("filters one psychological dimension independently from other tasks", () => {
    expect(filterBackgroundPasses(passes, "trait:ocean").map((pass) => pass.id)).toEqual([8, 6]);
    expect(filterBackgroundPasses(passes, "summary").map((pass) => pass.id)).toEqual([5]);
    expect(filterBackgroundPasses(passes, "all")).toEqual(passes);
  });

  it("keeps unclassified and future trait dimensions discoverable", () => {
    const extended = backgroundPasses([
      ...passes,
      t({ id: 10, stage: "trait", dimension: null }),
      t({ id: 9, stage: "trait", dimension: "future_dimension" }),
    ]);
    const categories = backgroundCategories(extended);

    expect(categories.some((category) => category.key === "trait:future_dimension")).toBe(true);
    expect(categories.some((category) => category.key === "trait:unclassified")).toBe(true);
    expect(filterBackgroundPasses(extended, "trait:unclassified").map((pass) => pass.id)).toEqual([10]);
  });
});

describe("parseSpan", () => {
  it("reads from/to out of the params JSON", () => {
    expect(parseSpan(t({ id: 1, stage: "trait", params: JSON.stringify({ from: 2, to: 9 }) })))
      .toEqual({ from: 2, to: 9 });
  });

  it("returns nulls when params is absent", () => {
    expect(parseSpan(t({ id: 1, stage: "trait", params: null }))).toEqual({ from: null, to: null });
  });
});

describe("userSnippet", () => {
  it("uses the lightweight snippet derived by the server", () => {
    expect(userSnippet(t({
      id: 1,
      stage: "chat",
      snippet: "what is the capital of France?",
    }))).toBe("what is the capital of France?");
  });

  it("returns null when no snippet is available", () => {
    expect(userSnippet(t({ id: 1, stage: "chat", snippet: null }))).toBeNull();
  });

  it("returns null for a null chat (round with no chat trace)", () => {
    expect(userSnippet(null)).toBeNull();
  });
});
