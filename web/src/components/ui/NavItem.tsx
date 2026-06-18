/** Left-rail nav entry: leading dot (glowing accent when active) + label, with an accent edge bar. */
export function NavItem({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={`flex items-center gap-2.5 rounded-lg border-l-2 px-3 py-2 text-left text-sm transition-colors ${
        active
          ? "border-accent bg-accent/10 text-ink"
          : "border-transparent text-muted hover:bg-white/5 hover:text-ink-soft"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 flex-none rounded-full ${
          active ? "bg-accent v-pulse" : "bg-muted/40"
        }`}
      />
      {label}
    </button>
  );
}
