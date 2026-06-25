import { describe, it, expect } from "vitest";
import { parseToolCalls } from "./toolcalls";

describe("parseToolCalls", () => {
  it("parses a JSON array of calls", () => {
    const raw = JSON.stringify([
      { name: "web_search", args: { query: "weather" }, result: "sunny", ok: true },
    ]);
    expect(parseToolCalls(raw)).toEqual([
      { name: "web_search", args: { query: "weather" }, result: "sunny", ok: true },
    ]);
  });

  it("returns [] for null (no tools, or pruned)", () => {
    expect(parseToolCalls(null)).toEqual([]);
  });

  it("returns [] for malformed JSON without throwing", () => {
    expect(parseToolCalls("{not json")).toEqual([]);
  });

  it("returns [] for a non-array payload", () => {
    expect(parseToolCalls(JSON.stringify({ name: "x" }))).toEqual([]);
  });
});
