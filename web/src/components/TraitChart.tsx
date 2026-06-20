import { useState } from "react";
import type { TraitDim } from "../api/client";
import { Card } from "./ui/Card";
import { traitRows, leaning, sparkline, type TraitRow } from "./traits/model";

// Ember Noir series — sienna, gold, sage, slate, ochre, plum (legible on the dark ground).
const COLORS = ["#D0663F", "#C6975A", "#9ABF82", "#8FB1C2", "#D9B36A", "#A98BC9"];
const SPARK_W = 64, SPARK_H = 18;
const COLLAPSED = 6;   // sorted dimensions (e.g. Schwartz) fold past this many rows

export function TraitChart({ dim }: { dim: TraitDim }) {
  const [expanded, setExpanded] = useState(false);
  const rows = traitRows(dim);
  const foldable = (dim.meta?.sort_by_score ?? false) && rows.length > COLLAPSED;
  const shown = foldable && !expanded ? rows.slice(0, COLLAPSED) : rows;

  return (
    <Card className="p-4">
      <div className="font-serif text-[15px] leading-tight text-ink">{dim.meta?.name ?? dim.dimension}</div>
      <div className="mb-3 mt-0.5 text-[10px] uppercase tracking-[0.1em] text-muted">
        {dim.sample_count} samples
      </div>
      {rows.length === 0 ? (
        <div className="text-xs text-muted">—</div>
      ) : (
        <div className="space-y-1.5">
          {shown.map((r, i) => <Row key={r.key} row={r} color={COLORS[i % COLORS.length]} />)}
        </div>
      )}
      {foldable && (
        <button
          onClick={() => setExpanded((v) => !v)}
          className="mt-2.5 text-[11px] tabular-nums text-muted transition-colors hover:text-ink-soft"
        >
          {expanded ? "▴" : `+${rows.length - COLLAPSED} ▾`}
        </button>
      )}
    </Card>
  );
}

function Spark({ values, color }: { values: number[]; color: string }) {
  const pts = sparkline(values, SPARK_W, SPARK_H);
  return (
    <svg width={SPARK_W} height={SPARK_H} className="flex-none overflow-visible">
      {pts && <polyline points={pts} fill="none" stroke={color} strokeWidth={1.25} strokeLinejoin="round" />}
    </svg>
  );
}

function Delta({ delta }: { delta: number | null }) {
  if (delta === null) return <span />;
  if (delta === 0) return <span className="text-right text-[10px] text-muted">0</span>;
  const up = delta > 0;
  return (
    <span className={`text-right text-[10px] tabular-nums ${up ? "text-status-pass-fg" : "text-accent-ink"}`}>
      {up ? "▲" : "▼"}{Math.abs(Math.round(delta))}
    </span>
  );
}

function Row({ row, color }: { row: TraitRow; color: string }) {
  const val = <span className="text-right tabular-nums text-ink-soft">{Math.round(row.score)}</span>;

  if (row.poles) {
    // bipolar — centered diverging bar: fill runs from the 50 midline out to the score
    const lean = leaning(row.score, row.poles);
    const lo = Math.min(row.score, 50), hi = Math.max(row.score, 50);
    const pole = (label: string, on: boolean) => (
      <span className={`text-center text-[11px] ${on ? "font-semibold text-gold" : "text-muted"}`}>{label}</span>
    );
    return (
      <div className="grid items-center gap-2 text-xs"
           style={{ gridTemplateColumns: `14px 1fr 14px 1.75rem ${SPARK_W}px 2.25rem` }}>
        {pole(row.poles[0], lean.side === "low")}
        <div className="relative h-1.5 rounded-full bg-line">
          <span className="absolute inset-y-[-2px] left-1/2 w-px bg-[#3a2f25]" />
          <span className="absolute inset-y-0 rounded-full"
                style={{ left: `${lo}%`, width: `${hi - lo}%`, background: color, opacity: 0.85 }} />
          <span className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink ring-2 ring-surface"
                style={{ left: `${row.score}%` }} />
        </div>
        {pole(row.poles[1], lean.side === "high")}
        {val}
        <Spark values={row.history} color={color} />
        <Delta delta={row.delta} />
      </div>
    );
  }

  // unipolar — left-anchored bar
  return (
    <div className="grid items-center gap-2 text-xs"
         style={{ gridTemplateColumns: `4.75rem 1fr 1.75rem ${SPARK_W}px 2.25rem` }}>
      <span className="truncate text-ink-soft" title={row.label}>{row.label}</span>
      <div className="relative h-1.5 overflow-hidden rounded-full bg-line">
        <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${row.score}%`, background: color }} />
      </div>
      {val}
      <Spark values={row.history} color={color} />
      <Delta delta={row.delta} />
    </div>
  );
}
