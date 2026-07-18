import { describe, expect, it } from "vitest";

import { diffPromptLines } from "./promptDiff";

describe("diffPromptLines", () => {
  it("keeps line numbers while showing removed and added Prompt text", () => {
    expect(diffPromptLines(
      "You are helpful.\nBe concise.\nMatch language.",
      "You are candid.\nBe concise.\nMatch language.\nAdd examples.",
    )).toEqual([
      { kind: "removed", text: "You are helpful.", baselineLine: 1, candidateLine: null },
      { kind: "added", text: "You are candid.", baselineLine: null, candidateLine: 1 },
      { kind: "same", text: "Be concise.", baselineLine: 2, candidateLine: 2 },
      { kind: "same", text: "Match language.", baselineLine: 3, candidateLine: 3 },
      { kind: "added", text: "Add examples.", baselineLine: null, candidateLine: 4 },
    ]);
  });

  it("handles an unavailable or empty baseline", () => {
    expect(diffPromptLines("", "New Prompt")).toEqual([
      { kind: "added", text: "New Prompt", baselineLine: null, candidateLine: 1 },
    ]);
  });
});
