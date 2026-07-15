import { useRef, useState } from "react";

import type { Fact } from "../../api/client";
import { FactMutationError } from "../../api/facts";
import { useT } from "../../i18n";
import { decideFactSave, FACT_TEXT_MAX_CHARS } from "./factEdit";
import { FactEditor } from "./FactEditor";

export function FactCard({
  fact,
  onSave,
  onDelete,
}: {
  fact: Fact;
  onSave: (id: number, text: string) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}) {
  const { t } = useT();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(fact.text);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);

  function cancel() {
    if (submitting.current) return;
    setDraft(fact.text);
    setError("");
    setEditing(false);
  }

  async function save() {
    if (submitting.current) return;
    const decision = decideFactSave(
      draft,
      fact.text,
      () => window.confirm(t("model.factSaveConfirm")),
    );
    if (decision.kind === "invalid") {
      setError(
        decision.reason === "empty"
          ? t("model.factEmptyError")
          : t("model.factTooLongError", { max: FACT_TEXT_MAX_CHARS }),
      );
      return;
    }
    if (decision.kind === "unchanged") {
      cancel();
      return;
    }
    if (decision.kind === "cancelled") return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await onSave(fact.id, decision.text);
      setEditing(false);
    } catch (cause) {
      if (cause instanceof FactMutationError && cause.status === 409) {
        setError(t("model.factDuplicateError"));
      } else if (cause instanceof FactMutationError && cause.status === 404) {
        setError(t("model.factStaleError"));
      } else {
        setError(t("model.factSaveFailed"));
      }
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  async function remove() {
    if (submitting.current || !window.confirm(t("model.factDeleteConfirm"))) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await onDelete(fact.id);
    } catch {
      setError(t("model.factDeleteFailed"));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  if (editing) {
    return (
      <FactEditor
        draft={draft}
        error={error}
        busy={busy}
        onDraft={(text) => {
          setDraft(text);
          if (error) setError("");
        }}
        onSave={() => void save()}
        onCancel={cancel}
        onLeave={() => void save()}
      />
    );
  }

  return (
    <li className="group rounded-xl border border-line bg-surface/55 px-4 py-3 transition-colors hover:border-muted/40">
      <div className="flex items-start gap-3">
        <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-gold" />
        <span className="min-w-0 flex-1 whitespace-pre-wrap leading-relaxed text-ink-soft">
          {fact.text}
        </span>
        <div className="flex flex-none items-center gap-1 opacity-100 transition-opacity sm:opacity-40 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
          <button
            type="button"
            disabled={busy}
            title={t("model.factEdit")}
            aria-label={t("model.factEdit")}
            onClick={() => {
              setDraft(fact.text);
              setError("");
              setEditing(true);
            }}
            className="rounded-md px-2 py-1 text-xs text-muted transition-colors hover:bg-well hover:text-ink disabled:opacity-50"
          >
            {t("model.factEdit")}
          </button>
          <button
            type="button"
            disabled={busy}
            title={t("model.factDelete")}
            aria-label={t("model.factDelete")}
            onClick={() => void remove()}
            className="rounded-md px-2 py-1 text-xs text-muted transition-colors hover:bg-status-fail-bg hover:text-status-fail-fg disabled:opacity-50"
          >
            {t("model.factDelete")}
          </button>
        </div>
      </div>
      {error && <div className="mt-2 pl-4 text-xs text-status-fail-fg">{error}</div>}
    </li>
  );
}
