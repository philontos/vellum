import { useState, type ReactNode } from "react";
import type { Trace } from "../../api/client";
import { useT } from "../../i18n";
import { Tag } from "../ui/StatusChip";
import { ReadingBlock } from "../ui/ReadingBlock";

// Stage → mark colour (echoes the chat ledger's page-edge marks).
const STAGE_DOT: Record<string, string> = {
  chat: "bg-accent",
  facts: "bg-status-pass-fg",
  trait: "bg-status-info-fg",
  summary: "bg-gold",
  dossier: "bg-status-warn-fg",
};

/**
 * One LLM-call trace: a one-line header (pin · stage · model · tokens · time)
 * with the heavy prompt/reasoning/output bodies collapsed behind Expand. Reused
 * for both the round view (chat/facts) and the background view (passes).
 */
export function TraceRow({
  trace, onPin, onNote, blur, badge,
}: {
  trace: Trace;
  onPin: (t: Trace) => void;
  onNote: (t: Trace, value: string) => void;
  blur: string;
  badge?: ReactNode;
}) {
  const { t: tr } = useT();
  const [open, setOpen] = useState(false);

  return (
    <div className="text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => onPin(trace)}
          title={tr("traces.pin")}
          className={trace.pinned ? "text-accent" : "text-muted transition-colors hover:text-ink-soft"}
        >
          {trace.pinned ? "★" : "☆"}
        </button>
        <span className={`h-1.5 w-1.5 flex-none rounded-full ${STAGE_DOT[trace.stage] ?? "bg-muted"}`} />
        <Tag>{trace.stage}</Tag>
        {badge}
        <span className="text-ink-soft">{trace.model}</span>
        <span className="font-mono text-[11px] text-muted">
          {trace.prompt_tokens ?? "?"}→{trace.completion_tokens ?? "?"} tok · {trace.duration_ms ?? "?"}ms
        </span>
        {trace.reasoning && <span title={tr("traces.hasReasoning")}>🧠</span>}
        <span className="ml-auto font-mono text-[11px] text-muted">{trace.created_at}</span>
        <button
          className="text-accent transition-colors hover:text-accent-ink"
          onClick={() => setOpen(!open)}
        >
          {open ? tr("traces.collapse") : tr("traces.expand")}
        </button>
      </div>
      {open && (
        <div className="mt-3 space-y-3">
          <input
            defaultValue={trace.note ?? ""}
            placeholder={tr("traces.notePh")}
            className={`w-full rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs text-ink-soft placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/20 ${blur}`}
            onBlur={(e) => onNote(trace, e.target.value)}
          />
          <ReadingBlock label="PROMPT" className={trace.prompt ? blur : ""}>
            {trace.prompt ?? <span className="text-muted">{tr("traces.pruned")}</span>}
          </ReadingBlock>
          {trace.reasoning && (
            <ReadingBlock label="REASONING" className={blur}>
              {trace.reasoning}
            </ReadingBlock>
          )}
          <ReadingBlock label="OUTPUT" className={trace.output ? blur : ""}>
            {trace.output ?? <span className="text-muted">{tr("traces.pruned")}</span>}
          </ReadingBlock>
        </div>
      )}
    </div>
  );
}
