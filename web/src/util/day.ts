// Day grouping helpers for time-broken lists (chat stream + diary timeline).

/** "YYYY-MM-DD" for grouping; empty when no timestamp. */
export function dayOf(ts?: string): string {
  return ts ? ts.slice(0, 10) : "";
}

/** A human day label: "今天"/"Today" for the current day, else a short date.
 * Tolerates sqlite "YYYY-MM-DD HH:MM:SS" (assumed UTC) and ISO strings. */
export function dayLabel(ts: string, lang: string): string {
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? ts.replace(" ", "T") : ts.replace(" ", "T") + "Z";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) return lang === "zh" ? "今天" : "Today";
  return lang === "zh"
    ? `${d.getMonth() + 1}月${d.getDate()}日`
    : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
