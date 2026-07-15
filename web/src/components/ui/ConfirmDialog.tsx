import { useEffect, useId, useRef, type KeyboardEvent } from "react";

export type ConfirmTone = "default" | "danger";

export type ConfirmDialogProps = {
  title: string;
  message: string;
  confirmLabel: string;
  cancelLabel: string;
  tone?: ConfirmTone;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  cancelLabel,
  tone = "default",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const messageId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    function escape(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [onCancel]);

  function trapFocus(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Tab") return;
    const buttons = Array.from(
      event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not([disabled])"),
    );
    if (buttons.length < 2) return;
    const first = buttons[0];
    const last = buttons[buttons.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <section
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={messageId}
        data-tone={tone}
        onKeyDown={trapFocus}
        className="w-full max-w-md overflow-hidden rounded-2xl border border-line bg-surface shadow-float"
      >
        <div className="h-1 bg-gradient-to-r from-transparent via-accent/80 to-transparent" />
        <div className="px-5 pb-5 pt-5 sm:px-6 sm:pb-6">
          <div className="flex items-start gap-4">
            <div
              aria-hidden="true"
              className={
                "flex h-9 w-9 flex-none items-center justify-center rounded-full border font-serif text-lg " +
                (tone === "danger"
                  ? "border-status-fail-fg/35 bg-status-fail-bg text-status-fail-fg"
                  : "border-accent/35 bg-well text-accent-ink")
              }
            >
              {tone === "danger" ? "!" : "?"}
            </div>
            <div className="min-w-0 flex-1">
              <h2 id={titleId} className="font-serif text-xl font-medium leading-tight text-ink">
                {title}
              </h2>
              <p id={messageId} className="mt-2 text-sm leading-relaxed text-ink-soft">
                {message}
              </p>
            </div>
          </div>
          <div className="mt-6 flex justify-end gap-2.5">
            <button
              ref={cancelRef}
              type="button"
              onClick={onCancel}
              className="min-h-10 rounded-lg border border-line bg-well px-4 text-sm text-ink-soft transition-colors hover:border-muted/50 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
            >
              {cancelLabel}
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className={
                "min-h-10 rounded-lg px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-surface " +
                (tone === "danger"
                  ? "bg-status-fail-fg text-[#1b0e0a] hover:bg-[#e7a08e] focus-visible:ring-status-fail-fg/70"
                  : "bg-accent text-white hover:bg-accent/85 focus-visible:ring-accent/70")
              }
            >
              {confirmLabel}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
