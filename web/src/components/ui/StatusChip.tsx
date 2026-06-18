import type { ReactNode } from "react";

// Run / case states → one of five harmonized, muted palettes.
const KIND: Record<string, string> = {
  pass: "bg-status-pass-bg text-status-pass-fg",
  done: "bg-status-pass-bg text-status-pass-fg",
  fail: "bg-status-fail-bg text-status-fail-fg",
  error: "bg-status-warn-bg text-status-warn-fg",
  scored: "bg-status-info-bg text-status-info-fg",
  running: "bg-status-neutral-bg text-status-neutral-fg",
};

const NEUTRAL = "bg-status-neutral-bg text-status-neutral-fg";

/** Small status pill (Evals run/case state). Unknown status → neutral. */
export function StatusChip({ status }: { status: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs ${KIND[status] ?? NEUTRAL}`}>
      {status}
    </span>
  );
}

/** Quiet neutral label pill — for non-status tags like a trace stage. */
export function Tag({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-full border border-line bg-surface px-2 py-0.5 text-xs text-muted">
      {children}
    </span>
  );
}
