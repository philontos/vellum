import type { ReactNode } from "react";

/** Raised surface: warm-dark panel, hairline border, soft shadow. */
export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={`rounded-xl border border-line bg-surface shadow-card ${className}`}>
      {children}
    </div>
  );
}
