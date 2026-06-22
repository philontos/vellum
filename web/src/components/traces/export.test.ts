import { describe, it, expect } from "vitest";
import type { Trace } from "../../api/client";
import { traceToJson, traceFilename } from "./export";

// Minimal Trace factory — only the fields a test cares about; the rest default.
function t(p: Partial<Trace> & { id: number; stage: string }): Trace {
  return {
    turn: null, model: "m", prompt: null, output: null, reasoning: null,
    prompt_tokens: null, completion_tokens: null, duration_ms: null,
    pinned: 0, note: null, created_at: "2026-06-20 10:00:00", params: null,
    ...p,
  };
}

describe("traceToJson", () => {
  it("expands a message-array prompt into a nested array", () => {
    const prompt = JSON.stringify([
      { role: "system", content: "you are…" },
      { role: "user", content: "今天…" },
    ]);
    const out = JSON.parse(traceToJson(t({ id: 1, stage: "chat", prompt })));
    expect(out.prompt).toEqual([
      { role: "system", content: "you are…" },
      { role: "user", content: "今天…" },
    ]);
  });

  it("expands a params blob into a nested object", () => {
    const params = JSON.stringify({ from: 10, to: 12 });
    const out = JSON.parse(traceToJson(t({ id: 1, stage: "trait", params })));
    expect(out.params).toEqual({ from: 10, to: 12 });
  });

  it("keeps a pruned (null) prompt/output as null", () => {
    const out = JSON.parse(traceToJson(t({ id: 1, stage: "chat", prompt: null, output: null })));
    expect(out.prompt).toBeNull();
    expect(out.output).toBeNull();
  });

  it("leaves an unparseable prompt as the raw string (no throw)", () => {
    const out = JSON.parse(traceToJson(t({ id: 1, stage: "facts", prompt: "Extract facts from…" })));
    expect(out.prompt).toBe("Extract facts from…");
  });

  it("only expands objects/arrays — a JSON-scalar prompt stays the raw string", () => {
    const out = JSON.parse(traceToJson(t({ id: 1, stage: "chat", prompt: "123" })));
    expect(out.prompt).toBe("123");
  });

  it("carries the metadata fields through verbatim", () => {
    const out = JSON.parse(traceToJson(t({
      id: 42, stage: "chat", model: "claude-x", turn: 7,
      prompt_tokens: 1203, completion_tokens: 456, duration_ms: 3200,
      note: "这轮塌了", created_at: "2026-06-21 09:00:00",
    })));
    expect(out).toMatchObject({
      id: 42, stage: "chat", model: "claude-x", turn: 7,
      prompt_tokens: 1203, completion_tokens: 456, duration_ms: 3200,
      note: "这轮塌了", created_at: "2026-06-21 09:00:00",
    });
  });

  it("pretty-prints with 2-space indentation", () => {
    const json = traceToJson(t({ id: 1, stage: "chat" }));
    expect(json).toContain('\n  "id": 1');
  });
});

describe("traceFilename", () => {
  it("builds vellum-trace-<id>-<stage>.json", () => {
    expect(traceFilename(t({ id: 142, stage: "chat" }))).toBe("vellum-trace-142-chat.json");
  });
});
