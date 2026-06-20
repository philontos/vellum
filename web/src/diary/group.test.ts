import { describe, expect, it } from "vitest";
import { groupByDay } from "./group";
import type { DiaryCard } from "../api/client";

const card = (id: number, created_at: string): DiaryCard => ({
  id,
  start_turn: 0,
  end_turn: 1,
  content: `c${id}`,
  created_at,
});

describe("groupByDay", () => {
  it("buckets consecutive cards of the same day, preserving order", () => {
    const days = groupByDay([
      card(3, "2026-06-20 10:00:00"),
      card(2, "2026-06-20 09:00:00"),
      card(1, "2026-06-19 22:00:00"),
    ]);
    expect(days.map((d) => d.day)).toEqual(["2026-06-20", "2026-06-19"]);
    expect(days[0].cards.map((c) => c.id)).toEqual([3, 2]);
    expect(days[1].cards.map((c) => c.id)).toEqual([1]);
  });

  it("returns an empty list for no cards", () => {
    expect(groupByDay([])).toEqual([]);
  });
});
