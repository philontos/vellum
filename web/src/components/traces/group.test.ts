import { describe, it, expect } from "vitest";
import type { Trace } from "../../api/client";
import { groupRounds, backgroundPasses, parseSpan, userSnippet } from "./group";

// Minimal Trace factory — only the fields a test cares about; the rest default.
function t(p: Partial<Trace> & { id: number; stage: string }): Trace {
  return {
    turn: null, model: "m", prompt: null, output: null, reasoning: null,
    prompt_tokens: null, completion_tokens: null, duration_ms: null,
    pinned: 0, note: null, created_at: "2026-06-20 10:00:00", params: null,
    tool_calls: null,
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

  it("ignores background stages (trait/summary/dossier/compact)", () => {
    const rounds = groupRounds([
      t({ id: 1, stage: "chat", turn: 1 }),
      t({ id: 2, stage: "trait", turn: 1 }),
      t({ id: 3, stage: "summary", turn: 1 }),
      t({ id: 4, stage: "dossier", turn: 1 }),
      t({ id: 5, stage: "compact", turn: 1 }),
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
  it("selects only trait/summary/dossier and parses the covered span", () => {
    const passes = backgroundPasses([
      t({ id: 1, stage: "chat", turn: 1 }),
      t({ id: 2, stage: "facts", turn: 1 }),
      t({ id: 3, stage: "trait", turn: 14, params: JSON.stringify({ from: 8, to: 14 }) }),
    ]);
    expect(passes).toHaveLength(1);
    expect(passes[0].stage).toBe("trait");
    expect(passes[0].from).toBe(8);
    expect(passes[0].to).toBe(14);
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
  it("extracts the last user message from the chat prompt JSON", () => {
    const prompt = JSON.stringify([
      { role: "system", content: "reference" },
      { role: "user", content: "what is the capital of France?" },
    ]);
    expect(userSnippet(t({ id: 1, stage: "chat", prompt }))).toBe("what is the capital of France?");
  });

  it("returns null when the prompt was pruned (null)", () => {
    expect(userSnippet(t({ id: 1, stage: "chat", prompt: null }))).toBeNull();
  });

  it("returns null when the prompt is not the expected message array", () => {
    expect(userSnippet(t({ id: 1, stage: "chat", prompt: "garbage" }))).toBeNull();
  });

  it("returns null for a null chat (round with no chat trace)", () => {
    expect(userSnippet(null)).toBeNull();
  });
});
