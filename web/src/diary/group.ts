import type { DiaryCard } from "../api/client";
import { dayOf } from "../util/day";

export type DiaryDay = { day: string; cards: DiaryCard[] };

/** Group cards (already newest-first) into consecutive same-day buckets,
 * preserving order — the diary timeline's day sections. */
export function groupByDay(cards: DiaryCard[]): DiaryDay[] {
  const out: DiaryDay[] = [];
  for (const c of cards) {
    const day = dayOf(c.created_at);
    const last = out[out.length - 1];
    if (last && last.day === day) last.cards.push(c);
    else out.push({ day, cards: [c] });
  }
  return out;
}
