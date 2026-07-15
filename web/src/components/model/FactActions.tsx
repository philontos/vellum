type FactActionsProps = {
  editLabel: string;
  deleteLabel: string;
  busy: boolean;
  onEdit: () => void;
  onDelete: () => void;
};

function PencilIcon() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" />
      <path d="m14.5 5.5 3 3" />
    </svg>
  );
}

function DeleteIcon() {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      className="h-4 w-4"
    >
      <path d="m6 6 12 12" />
      <path d="M18 6 6 18" />
    </svg>
  );
}

export function FactActions({
  editLabel,
  deleteLabel,
  busy,
  onEdit,
  onDelete,
}: FactActionsProps) {
  return (
    <div
      data-fact-actions="compact"
      data-layout="vertical"
      className="flex w-10 flex-none flex-col items-center gap-1 opacity-100 transition-opacity sm:opacity-40 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
    >
      <button
        type="button"
        disabled={busy}
        title={editLabel}
        aria-label={editLabel}
        onClick={onEdit}
        className="flex h-10 w-10 items-center justify-center rounded-lg text-muted transition-colors hover:bg-well hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:opacity-50"
      >
        <PencilIcon />
      </button>
      <button
        type="button"
        disabled={busy}
        title={deleteLabel}
        aria-label={deleteLabel}
        onClick={onDelete}
        className="flex h-10 w-10 items-center justify-center rounded-lg text-muted transition-colors hover:bg-status-fail-bg hover:text-status-fail-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-status-fail-fg/60 disabled:opacity-50"
      >
        <DeleteIcon />
      </button>
    </div>
  );
}
