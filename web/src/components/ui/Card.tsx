import type { ReactNode } from "react";

/** Raised paper surface: white card, hairline border, soft warm shadow. */
export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <div className={`rounded-xl border border-card-line bg-card shadow-card ${className}`}>
      {children}
    </div>
  );
}
