import { describe, expect, it } from "vitest";

import { diaryEntryPath, diaryTimelinePath, parseDiaryRoute } from "./route";

describe("Diary browser routes", () => {
  it("builds stable timeline and entry page URLs", () => {
    expect(diaryTimelinePath()).toBe("/app/diary");
    expect(diaryEntryPath(42)).toBe("/app/diary/42");
  });

  it("parses timeline and entry pages while rejecting API and malformed paths", () => {
    expect(parseDiaryRoute("/app/diary")).toEqual({ kind: "timeline" });
    expect(parseDiaryRoute("/app/diary/")).toEqual({ kind: "timeline" });
    expect(parseDiaryRoute("/app/diary/42")).toEqual({ kind: "entry", entryId: 42 });
    expect(parseDiaryRoute("/diary/42")).toEqual({ kind: "other" });
    expect(parseDiaryRoute("/app/diary/nope")).toEqual({ kind: "other" });
  });
});
