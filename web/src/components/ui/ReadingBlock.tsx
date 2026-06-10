import type { ReactNode } from "react";

/**
 * Labeled reading block for prompt / reasoning / output bodies.
 * Monospace-free, warm paper well, whitespace preserved.
 */
export function ReadingBlock({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div>
      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">{label}</div>
      <pre
        className={`max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-paper-raised p-3 font-sans text-xs leading-relaxed text-ink-soft ${className}`}
      >
        {children}
      </pre>
    </div>
  );
}
