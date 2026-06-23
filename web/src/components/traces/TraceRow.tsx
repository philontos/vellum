import { useState, type ReactNode } from "react";
import type { Trace } from "../../api/client";
import { useT } from "../../i18n";
import { copyText, downloadText } from "../../util/transfer";
import { Tag } from "../ui/StatusChip";
import { ReadingBlock } from "../ui/ReadingBlock";
import { traceFilename, traceToJson } from "./export";

// Stage → mark colour (echoes the chat ledger's page-edge marks).
const STAGE_DOT: Record<string, string> = {
  chat: "bg-accent",
  facts: "bg-status-pass-fg",
  compact: "bg-status-pass-fg", // facts-family green; never shares a tab with facts
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
  const [copied, setCopied] = useState(false);

  async function copy() {
    if (await copyText(traceToJson(trace))) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

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
          onClick={copy}
          title={copied ? tr("traces.copied") : tr("traces.copy")}
          className={copied ? "text-status-pass-fg" : "text-muted transition-colors hover:text-ink-soft"}
        >
          {copied ? "✓" : "📋"}
        </button>
        <button
          onClick={() => downloadText(traceFilename(trace), traceToJson(trace))}
          title={tr("traces.download")}
          className="text-muted transition-colors hover:text-ink-soft"
        >
          ⬇
        </button>
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
