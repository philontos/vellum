import { useRef, useState } from "react";

import type { Fact } from "../../api/client";
import { FactMutationError } from "../../api/facts";
import { useConfirm } from "../../confirm/ConfirmProvider";
import { useT } from "../../i18n";
import { FACT_TEXT_MAX_CHARS, validateFactDraft } from "./factEdit";
import { FactActions } from "./FactActions";
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
  const confirm = useConfirm();
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
    const decision = validateFactDraft(draft, fact.text);
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
    submitting.current = true;
    setBusy(true);
    const approved = await confirm({
      title: t("model.factSaveTitle"),
      message: t("model.factSaveConfirm"),
      confirmLabel: t("dialog.save"),
      cancelLabel: t("dialog.cancel"),
    });
    if (!approved) {
      submitting.current = false;
      setBusy(false);
      return;
    }
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
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    const approved = await confirm({
      title: t("model.factDeleteTitle"),
      message: t("model.factDeleteConfirm"),
      confirmLabel: t("dialog.delete"),
      cancelLabel: t("dialog.cancel"),
      tone: "danger",
    });
    if (!approved) {
      submitting.current = false;
      setBusy(false);
      return;
    }
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
    <li className="group rounded-xl border border-line bg-surface/55 px-3 py-3 transition-colors hover:border-muted/40 sm:px-4">
      <div className="grid grid-cols-[auto_minmax(0,1fr)_2.5rem] items-start gap-x-2.5">
        <span className="mt-[7px] h-1.5 w-1.5 flex-none rounded-full bg-gold" />
        <span className="min-w-0 flex-1 whitespace-pre-wrap leading-relaxed text-ink-soft">
          {fact.text}
        </span>
        <FactActions
          editLabel={t("model.factEdit")}
          deleteLabel={t("model.factDelete")}
          busy={busy}
          onEdit={() => {
            setDraft(fact.text);
            setError("");
            setEditing(true);
          }}
          onDelete={() => void remove()}
        />
      </div>
      {error && <div className="mt-2 pl-4 text-xs text-status-fail-fg">{error}</div>}
    </li>
  );
}
