import { describe, expect, it, vi } from "vitest";

import { allowViewChange } from "./App";

describe("allowViewChange", () => {
  it("blocks leaving Prompts when the local editor is dirty and discard is declined", () => {
    const confirmDiscard = vi.fn(() => false);

    expect(allowViewChange("prompts", true, confirmDiscard)).toBe(false);
    expect(confirmDiscard).toHaveBeenCalledOnce();
  });

  it("does not ask when no local Prompt edit would be lost", () => {
    const confirmDiscard = vi.fn(() => false);

    expect(allowViewChange("chat", true, confirmDiscard)).toBe(true);
    expect(allowViewChange("prompts", false, confirmDiscard)).toBe(true);
    expect(confirmDiscard).not.toHaveBeenCalled();
  });
});
