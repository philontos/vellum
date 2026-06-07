import type { TraitDim } from "../api/client";

const W = 280, H = 90, PAD = 6;

export function TraitChart({ dim }: { dim: TraitDim }) {
  const subs = Object.entries(dim.content_json)
    .filter(([, v]) => typeof v?.score === "number")
    .map(([k, v]) => [k, v.score as number] as const);

  // history → one polyline per sub-dimension (score 0..100)
  const pts = dim.history.length;
  const x = (i: number) => PAD + (pts <= 1 ? 0 : (i * (W - 2 * PAD)) / (pts - 1));
  const y = (score: number) => H - PAD - (score / 100) * (H - 2 * PAD);
  const colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2"];

  return (
    <div className="rounded-xl border border-gray-200 p-3">
      <div className="mb-2 text-sm font-semibold">{dim.dimension}</div>
      {subs.map(([k, score], i) => (
        <div key={k} className="mb-1 flex items-center gap-2 text-xs">
          <span className="w-6 text-gray-500">{k}</span>
          <div className="h-2 flex-1 rounded bg-gray-100">
            <div className="h-2 rounded" style={{ width: `${score}%`, background: colors[i % colors.length] }} />
          </div>
          <span className="w-8 text-right tabular-nums">{Math.round(score)}</span>
        </div>
      ))}
      {pts > 1 && (
        <svg width={W} height={H} className="mt-2 w-full">
          {subs.map(([k], i) => {
            const path = dim.history
              .map((h, idx) => `${idx ? "L" : "M"}${x(idx)},${y(h.content_json[k]?.score ?? 50)}`)
              .join(" ");
            return <path key={k} d={path} fill="none" stroke={colors[i % colors.length]} strokeWidth="1.5" />;
          })}
        </svg>
      )}
    </div>
  );
}
