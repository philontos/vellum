import { useState } from "react";
import type { TraceSummary, TurnRun } from "../../api/client";
import { useT } from "../../i18n";
import { type Round, userSnippet } from "./group";
import { TraceRow } from "./TraceRow";
import { StatusChip, Tag } from "../ui/StatusChip";

/**
 * One conversation round: a collapsible header (turn · user's question · time)
 * over the round's chat trace and the facts extraction(s) it triggered. Expanded
 * by default; each inner trace's body stays collapsed until expanded.
 */
export function RoundCard({
  round, run, onPin, onNote,
}: {
  round: Round;
  run?: TurnRun;
  onPin: (t: TraceSummary) => void;
  onNote: (t: TraceSummary, value: string) => void;
}) {
  const { t: tr } = useT();
  const [open, setOpen] = useState(true);
  const snippet = userSnippet(round.chat)
    ?? round.controller.find((trace) => trace.snippet)?.snippet
    ?? null;
  const rows: TraceSummary[] = [
    ...round.controller,
    ...(round.chat ? [round.chat] : []),
    ...round.facts,
  ];
  const synthesisBasis = typeof run?.decision?.synthesis_basis === "string"
    ? run.decision.synthesis_basis.replace(/_/g, " ")
    : null;

  return (
    <div className="border-b border-line/70">
      <button
        onClick={() => setOpen(!open)}
        className="flex min-h-11 w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-white/5 sm:px-4"
      >
        <span className="flex-none text-muted">{open ? "▾" : "▸"}</span>
        <span className="flex-none font-mono text-[11px] text-muted">
          {round.turn === null ? tr("traces.ungrouped") : tr("traces.roundTurn", { turn: round.turn })}
        </span>
        {snippet && <span className="min-w-0 flex-1 truncate text-sm text-ink-soft">{snippet}</span>}
        {run?.route && <Tag>{run.route}</Tag>}
        {run && <StatusChip status={run.status} />}
        <span className="ml-auto hidden flex-none font-mono text-[11px] text-muted sm:inline">{round.chat?.created_at ?? ""}</span>
      </button>
      {open && (
        <div className="space-y-3 px-3 pb-3 sm:px-4 sm:pl-8">
          {run && (
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
              {run.inquiry_id !== null && <Tag>Inquiry #{run.inquiry_id}</Tag>}
              {synthesisBasis && <Tag>{synthesisBasis}</Tag>}
              {(run.revision_before !== null || run.revision_after !== null) && (
                <Tag>rev {run.revision_before ?? "—"}→{run.revision_after ?? "—"}</Tag>
              )}
              <RunContextMeta run={run} />
              {run.error && <span className="text-status-warn-fg">{run.error}</span>}
            </div>
          )}
          {rows.map((t) => (
            <TraceRow key={t.id} trace={t} onPin={onPin} onNote={onNote} />
          ))}
        </div>
      )}
    </div>
  );
}


function RunContextMeta({ run }: { run: TurnRun }) {
  const { t } = useT();
  const number = (key: string) => {
    const value = run.context_meta[key];
    return typeof value === "number" ? value : null;
  };
  const estimated = number("estimated_tokens");
  const maxTokens = number("max_input_tokens");
  const remainingQuestions = number("remaining_questions");
  const maxQuestions = number("max_questions");
  const dropped = (number("dropped_recent_messages") ?? 0)
    + (number("dropped_assistant_messages") ?? 0)
    + (number("dropped_cited_evidence") ?? 0)
    + (number("dropped_paused_inquiries") ?? 0)
    + (number("dropped_recent_episodes") ?? 0)
    + (number("dropped_state_snapshots") ?? 0);
  const responder = (
    run.context_meta.responder
    && typeof run.context_meta.responder === "object"
    && !Array.isArray(run.context_meta.responder)
  ) ? run.context_meta.responder as Record<string, unknown> : null;
  const responderNumber = (key: string) => {
    const value = responder?.[key];
    return typeof value === "number" ? value : null;
  };
  const responderMode = typeof responder?.context_mode === "string"
    ? responder.context_mode
    : null;
  const responderEstimated = responderNumber("estimated_tokens");
  const responderMax = responderNumber("max_input_tokens");
  const responderDropped = (responderNumber("dropped_history_messages") ?? 0)
    + (responderNumber("dropped_recall_snippets") ?? 0)
    + (responderNumber("dropped_facts") ?? 0);
  const normalizedFields = Array.isArray(
    run.context_meta.controller_normalized_fields,
  ) ? run.context_meta.controller_normalized_fields.filter(
      (value): value is string => typeof value === "string",
    ) : [];

  return (
    <>
      {estimated !== null && maxTokens !== null && (
        <Tag>{t("traces.contextTokens", { used: estimated, max: maxTokens })}</Tag>
      )}
      {remainingQuestions !== null && maxQuestions !== null && (
        <Tag>{t("traces.questionBudget", {
          remaining: remainingQuestions, max: maxQuestions,
        })}</Tag>
      )}
      {dropped > 0 && <Tag>{t("traces.contextDropped", { n: dropped })}</Tag>}
      {run.context_meta.current_user_turn_truncated === true && (
        <Tag>{t("traces.currentTurnTruncated")}</Tag>
      )}
      {responderMode && responderEstimated !== null && responderMax !== null && (
        <Tag>{t("traces.responderContext", {
          mode: responderMode, used: responderEstimated, max: responderMax,
        })}</Tag>
      )}
      {responderDropped > 0 && (
        <Tag>{t("traces.responderDropped", { n: responderDropped })}</Tag>
      )}
      {responder?.current_message_truncated === true && (
        <Tag>{t("traces.responderCurrentTurnTruncated")}</Tag>
      )}
      {normalizedFields.length > 0 && (
        <Tag>{t("traces.controllerNormalized", {
          fields: normalizedFields.join(", "),
        })}</Tag>
      )}
    </>
  );
}
