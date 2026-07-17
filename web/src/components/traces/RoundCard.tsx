import { useState } from "react";
import type { TraceSummary } from "../../api/client";
import { useT } from "../../i18n";
import { type Round, userSnippet } from "./group";
import { TraceRow } from "./TraceRow";

/**
 * One conversation round: a collapsible header (turn · user's question · time)
 * over the round's chat trace and the facts extraction(s) it triggered. Expanded
 * by default; each inner trace's body stays collapsed until expanded.
 */
export function RoundCard({
  round, onPin, onNote,
}: {
  round: Round;
  onPin: (t: TraceSummary) => void;
  onNote: (t: TraceSummary, value: string) => void;
}) {
  const { t: tr } = useT();
  const [open, setOpen] = useState(true);
  const snippet = userSnippet(round.chat);
  const rows: TraceSummary[] = [...(round.chat ? [round.chat] : []), ...round.facts];

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
        <span className="ml-auto hidden flex-none font-mono text-[11px] text-muted sm:inline">{round.chat?.created_at ?? ""}</span>
      </button>
      {open && (
        <div className="space-y-3 px-3 pb-3 sm:px-4 sm:pl-8">
          {rows.map((t) => (
            <TraceRow key={t.id} trace={t} onPin={onPin} onNote={onNote} />
          ))}
        </div>
      )}
    </div>
  );
}
