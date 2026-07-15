import { describe, expect, it, vi } from "vitest";

import { FACT_TEXT_MAX_CHARS, decideFactSave } from "./factEdit";


describe("decideFactSave", () => {
  it("rejects blank text without asking for confirmation", () => {
    const confirm = vi.fn(() => true);

    expect(decideFactSave("   ", "old", confirm)).toEqual({
      kind: "invalid",
      reason: "empty",
    });
    expect(confirm).not.toHaveBeenCalled();
  });

  it("rejects text beyond the server limit without confirming", () => {
    const confirm = vi.fn(() => true);

    expect(decideFactSave("x".repeat(FACT_TEXT_MAX_CHARS + 1), "old", confirm)).toEqual({
      kind: "invalid",
      reason: "too_long",
    });
    expect(confirm).not.toHaveBeenCalled();
  });

  it("trims an actual change and asks once before saving", () => {
    const confirm = vi.fn(() => true);

    expect(decideFactSave("  clearer  ", "old", confirm)).toEqual({
      kind: "save",
      text: "clearer",
    });
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it("does not confirm or submit unchanged text", () => {
    const confirm = vi.fn(() => true);

    expect(decideFactSave("  old  ", "old", confirm)).toEqual({ kind: "unchanged" });
    expect(confirm).not.toHaveBeenCalled();
  });

  it("keeps editing when the user declines confirmation", () => {
    expect(decideFactSave("new", "old", () => false)).toEqual({ kind: "cancelled" });
  });
});
