import type { ReactNode } from "react";

/** Uppercase micro-label + a hairline rule that fills the remaining width. */
export function SectionHeader({ label, right }: { label: string; right?: ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline gap-3">
      <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">{label}</span>
      <span className="h-px flex-1 bg-line" />
      {right}
    </div>
  );
}
