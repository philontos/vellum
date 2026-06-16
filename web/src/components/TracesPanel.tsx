import { useEffect, useState } from "react";
import { getTraces, patchTrace, type Trace } from "../api/client";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";
import { Tag } from "./ui/StatusChip";
import { ReadingBlock } from "./ui/ReadingBlock";

const STAGES = ["", "chat", "facts", "trait", "summary", "dossier"];

export function TracesPanel() {
  const { t: tr } = useT();
  const blur = usePrivacyBlur();
  const [stage, setStage] = useState("");
  const [rows, setRows] = useState<Trace[]>([]);
  const [open, setOpen] = useState<number | null>(null);

  async function load() {
    setRows(await getTraces(stage || undefined));
  }
  useEffect(() => { load().catch(() => void 0); }, [stage]);

  async function pin(t: Trace) {
    await patchTrace(t.id, { pinned: !t.pinned });
    load();
  }
  async function note(t: Trace, value: string) {
    await patchTrace(t.id, { note: value });
    load();
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm">
        <select
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          className="rounded-lg border border-card-line bg-card px-2.5 py-1.5 text-ink-soft focus:outline-none focus:ring-2 focus:ring-terracotta/15"
        >
          {STAGES.map((s) => <option key={s} value={s}>{s || tr("traces.allStages")}</option>)}
        </select>
        <button
          onClick={() => load()}
          className="rounded-lg border border-card-line bg-card px-3 py-1.5 text-ink-soft transition-colors hover:bg-paper-raised"
        >
          {tr("traces.refresh")}
        </button>
        <span className="text-muted">{tr("traces.count", { n: rows.length })}</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {rows.map((t) => (
          <div key={t.id} className="border-b border-line/70 px-4 py-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => pin(t)}
                title={tr("traces.pin")}
                className={t.pinned ? "text-terracotta" : "text-muted transition-colors hover:text-ink-soft"}
              >
                {t.pinned ? "★" : "☆"}
              </button>
              <Tag>{t.stage}</Tag>
              <span className="text-ink-soft">{t.model}</span>
              <span className="text-xs text-muted">
                {t.prompt_tokens ?? "?"}→{t.completion_tokens ?? "?"} tok · {t.duration_ms ?? "?"}ms
              </span>
              {t.reasoning && <span title={tr("traces.hasReasoning")}>🧠</span>}
              <span className="ml-auto text-xs text-muted">{t.created_at}</span>
              <button
                className="text-terracotta-ink transition-colors hover:text-terracotta"
                onClick={() => setOpen(open === t.id ? null : t.id)}
              >
                {open === t.id ? tr("traces.collapse") : tr("traces.expand")}
              </button>
            </div>
            {open === t.id && (
              <div className="mt-3 space-y-3">
                <input
                  defaultValue={t.note ?? ""}
                  placeholder={tr("traces.notePh")}
                  className={`w-full rounded-lg border border-card-line bg-card px-2.5 py-1.5 text-xs text-ink-soft placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-terracotta/15 ${blur}`}
                  onBlur={(e) => note(t, e.target.value)}
                />
                <ReadingBlock label="PROMPT" className={t.prompt ? blur : ""}>
                  {t.prompt ?? <span className="text-muted">{tr("traces.pruned")}</span>}
                </ReadingBlock>
                {t.reasoning && (
                  <ReadingBlock label="REASONING" className={blur}>
                    {t.reasoning}
                  </ReadingBlock>
                )}
                <ReadingBlock label="OUTPUT" className={t.output ? blur : ""}>
                  {t.output ?? <span className="text-muted">{tr("traces.pruned")}</span>}
                </ReadingBlock>
              </div>
            )}
          </div>
        ))}
        {rows.length === 0 && <div className="p-8 text-muted">{tr("traces.empty")}</div>}
      </div>
    </div>
  );
}
