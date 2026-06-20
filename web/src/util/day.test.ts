import { describe, expect, it } from "vitest";
import { dayOf, dayLabel } from "./day";

describe("dayOf", () => {
  it("returns the YYYY-MM-DD date portion", () => {
    expect(dayOf("2026-06-20 10:30:00")).toBe("2026-06-20");
  });
  it("returns empty string when there is no timestamp", () => {
    expect(dayOf(undefined)).toBe("");
  });
});

describe("dayLabel", () => {
  it("labels a past date in Chinese", () => {
    expect(dayLabel("2020-01-05 12:00:00", "zh")).toBe("1月5日");
  });
  it("labels a past date in English", () => {
    expect(dayLabel("2020-01-05 12:00:00", "en")).toBe("Jan 5");
  });
});
