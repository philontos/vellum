/** Left-rail nav entry: leading dot (terracotta when active) + label. */
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
      className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
        active
          ? "bg-card font-semibold text-ink shadow-card"
          : "text-muted hover:bg-paper-raised hover:text-ink-soft"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 flex-none rounded-full ${active ? "bg-terracotta" : "bg-transparent"}`}
      />
      {label}
    </button>
  );
}
