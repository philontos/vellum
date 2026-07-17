import { useRef, useState, type ReactNode } from "react";
import { getTrace, type Trace, type TraceSummary } from "../../api/client";
import { useT } from "../../i18n";
import { copyText, downloadText } from "../../util/transfer";
import { Tag } from "../ui/StatusChip";
import { ReadingBlock } from "../ui/ReadingBlock";
import { traceFilename, traceToJson } from "./export";
import { parseToolCalls } from "./toolcalls";

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
  trace, onPin, onNote, badge,
}: {
  trace: TraceSummary;
  onPin: (t: TraceSummary) => void;
  onNote: (t: TraceSummary, value: string) => void;
  badge?: ReactNode;
}) {
  const { t: tr } = useT();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [detail, setDetail] = useState<Trace | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const pendingDetail = useRef<Promise<Trace | null> | null>(null);
  const toolCalls = parseToolCalls(detail?.tool_calls ?? null);

  function loadDetail(): Promise<Trace | null> {
    if (detail) return Promise.resolve(detail);
    if (pendingDetail.current) return pendingDetail.current;

    setDetailLoading(true);
    setDetailError("");
    const request = getTrace(trace.id)
      .then((loaded) => {
        setDetail(loaded);
        return loaded;
      })
      .catch((error: unknown) => {
        setDetailError(error instanceof Error ? error.message : String(error));
        return null;
      })
      .finally(() => {
        setDetailLoading(false);
        pendingDetail.current = null;
      });
    pendingDetail.current = request;
    return request;
  }

  function toggleDetail() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    void loadDetail();
  }

  async function copy() {
    const loaded = await loadDetail();
    if (loaded && await copyText(traceToJson(loaded))) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  async function download() {
    const loaded = await loadDetail();
    if (loaded) downloadText(traceFilename(loaded), traceToJson(loaded));
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
        {trace.has_reasoning && <span title={tr("traces.hasReasoning")}>🧠</span>}
        {trace.has_tool_calls && <span title={tr("traces.hasTools")}>🔧</span>}
        <span className="w-full font-mono text-[11px] text-muted sm:ml-auto sm:w-auto">{trace.created_at}</span>
        <button
          onClick={copy}
          title={copied ? tr("traces.copied") : tr("traces.copy")}
          className={copied ? "text-status-pass-fg" : "text-muted transition-colors hover:text-ink-soft"}
        >
          {copied ? "✓" : "📋"}
        </button>
        <button
          onClick={() => void download()}
          title={tr("traces.download")}
          className="text-muted transition-colors hover:text-ink-soft"
        >
          ⬇
        </button>
        <button
          className="text-accent transition-colors hover:text-accent-ink"
          onClick={toggleDetail}
        >
          {open ? tr("traces.collapse") : tr("traces.expand")}
        </button>
      </div>
      {open && (
        <div className="mt-3 space-y-3">
          <input
            defaultValue={trace.note ?? ""}
            placeholder={tr("traces.notePh")}
            className="min-h-11 w-full rounded-lg border border-line bg-surface px-2.5 py-1.5 text-base sm:text-xs text-ink-soft placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/20"
            onBlur={(e) => onNote(trace, e.target.value)}
          />
          {detailLoading && !detail && (
            <div className="rounded-lg border border-line bg-surface px-3 py-4 text-muted">
              {tr("traces.detailLoading")}
            </div>
          )}
          {detailError && !detail && (
            <div role="alert" className="rounded-lg border border-status-fail-fg/30 bg-status-fail-bg px-3 py-3 text-status-fail-fg">
              <div>{tr("traces.detailFailed")}</div>
              <div className="mt-1 font-mono text-[11px] opacity-80">{detailError}</div>
              <button
                type="button"
                onClick={() => void loadDetail()}
                className="mt-2 rounded-md border border-current/30 px-2.5 py-1 text-xs transition-colors hover:bg-white/5"
              >
                {tr("traces.retry")}
              </button>
            </div>
          )}
          {detail && (
            <>
              <ReadingBlock label="PROMPT">
                {detail.prompt ?? <span className="text-muted">{tr("traces.pruned")}</span>}
              </ReadingBlock>
              {detail.reasoning && (
                <ReadingBlock label="REASONING">
                  {detail.reasoning}
                </ReadingBlock>
              )}
              {toolCalls.length > 0 && (
                <div className="space-y-2">
                  <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
                    {tr("traces.toolCalls")}
                  </div>
                  {toolCalls.map((c, i) => (
                    <div key={i} className="space-y-1.5 border-l-2 border-line pl-3">
                      <div className="flex items-center gap-2 text-xs">
                        <span className={c.ok === false ? "text-status-fail-fg" : "text-status-pass-fg"}>
                          {c.ok === false ? "✗" : "✓"}
                        </span>
                        <span className="font-mono text-ink-soft">{c.name}</span>
                      </div>
                      <ReadingBlock label="ARGS">
                        {c.raw_args ?? JSON.stringify(c.args ?? {}, null, 2)}
                      </ReadingBlock>
                      {c.result != null && (
                        <ReadingBlock label="RESULT">
                          {c.result}
                        </ReadingBlock>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <ReadingBlock label="OUTPUT">
                {detail.output ?? <span className="text-muted">{tr("traces.pruned")}</span>}
              </ReadingBlock>
            </>
          )}
        </div>
      )}
    </div>
  );
}
