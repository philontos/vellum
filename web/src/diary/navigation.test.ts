import { describe, expect, it } from "vitest";

import { isDiaryBackSwipe } from "./navigation";

describe("isDiaryBackSwipe", () => {
  it("accepts a deliberate right swipe", () => {
    expect(isDiaryBackSwipe({ x: 20, y: 100 }, { x: 120, y: 112 })).toBe(true);
  });

  it("ignores leftward, short, and mostly vertical gestures", () => {
    expect(isDiaryBackSwipe({ x: 120, y: 100 }, { x: 20, y: 100 })).toBe(false);
    expect(isDiaryBackSwipe({ x: 20, y: 100 }, { x: 70, y: 100 })).toBe(false);
    expect(isDiaryBackSwipe({ x: 20, y: 100 }, { x: 105, y: 190 })).toBe(false);
  });
});
