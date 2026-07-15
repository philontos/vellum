import { describe, expect, it } from "vitest";

import { FACT_TEXT_MAX_CHARS, validateFactDraft } from "./factEdit";


describe("validateFactDraft", () => {
  it("rejects blank text", () => {
    expect(validateFactDraft("   ", "old")).toEqual({
      kind: "invalid",
      reason: "empty",
    });
  });

  it("rejects text beyond the server limit", () => {
    expect(validateFactDraft("x".repeat(FACT_TEXT_MAX_CHARS + 1), "old")).toEqual({
      kind: "invalid",
      reason: "too_long",
    });
  });

  it("trims an actual change before confirmation", () => {
    expect(validateFactDraft("  clearer  ", "old")).toEqual({
      kind: "changed",
      text: "clearer",
    });
  });

  it("does not submit unchanged text", () => {
    expect(validateFactDraft("  old  ", "old")).toEqual({ kind: "unchanged" });
  });
});
