import type { TraitDim } from "../api/client";
import { Card } from "./ui/Card";

const W = 280, H = 90, PAD = 6;

// Ember Noir series — sienna, gold, sage, slate, ochre, plum (legible on the dark ground).
const COLORS = ["#D0663F", "#C6975A", "#9ABF82", "#8FB1C2", "#D9B36A", "#A98BC9"];

export function TraitChart({ dim }: { dim: TraitDim }) {
  const subs = Object.entries(dim.content_json)
    .filter(([, v]) => typeof v?.score === "number")
    .map(([k, v]) => [k, v.score as number] as const);

  // history → one polyline per sub-dimension (score 0..100)
  const pts = dim.history.length;
  const x = (i: number) => PAD + (pts <= 1 ? 0 : (i * (W - 2 * PAD)) / (pts - 1));
  const y = (score: number) => H - PAD - (score / 100) * (H - 2 * PAD);

  return (
    <Card className="p-4">
      <div className="mb-3 font-serif text-[15px] text-ink">{dim.dimension}</div>
      {subs.map(([k, score], i) => (
        <div key={k} className="mb-1.5 flex items-center gap-2 text-xs">
          <span className="w-6 text-muted">{k}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line">
            <div
              className="h-full rounded-full"
              style={{ width: `${score}%`, background: COLORS[i % COLORS.length] }}
            />
          </div>
          <span className="w-8 text-right tabular-nums text-ink-soft">{Math.round(score)}</span>
        </div>
      ))}
      {pts > 1 && (
        <svg width={W} height={H} className="mt-3 w-full">
          {subs.map(([k], i) => {
            const path = dim.history
              .map((h, idx) => `${idx ? "L" : "M"}${x(idx)},${y(h.content_json[k]?.score ?? 50)}`)
              .join(" ");
            return <path key={k} d={path} fill="none" stroke={COLORS[i % COLORS.length]} strokeWidth="1.5" />;
          })}
        </svg>
      )}
    </Card>
  );
}
