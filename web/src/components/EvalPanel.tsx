import { useEffect, useState } from "react";
import {
  getEvalRuns, getEvalRun, streamEvalRun,
  type EvalSuite, type EvalRun, type EvalRunDetail, type EvalCaseEvent,
} from "../api/client";
import { useT } from "../i18n";
import { StatusChip, Tag } from "./ui/StatusChip";

type Live = { suite: string; total: number; completed: number; cases: EvalCaseEvent[] };

function summarize(obj: Record<string, unknown> | null | undefined): string {
  if (!obj) return "";
  return Object.entries(obj).map(([k, v]) => `${k} ${v}`).join(" · ");
}

export function EvalPanel() {
  const { t } = useT();
  const [suites, setSuites] = useState<EvalSuite[]>([]);
  const [suite, setSuite] = useState("");
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [live, setLive] = useState<Live | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);

  async function load() {
    const r = await getEvalRuns();
    setRuns(r.runs);
    setSuites(r.suites);
    if (!suite && r.suites.length) setSuite(r.suites[0].key);
  }
  useEffect(() => { load().catch(() => void 0); }, []);

  const selected = suites.find((s) => s.key === suite);

  async function run() {
    if (!suite || live) return;
    setLive({ suite, total: 0, completed: 0, cases: [] });
    try {
      await streamEvalRun(suite, {
        onRun: (m) => setLive({ suite: m.suite, total: m.total, completed: 0, cases: [] }),
        onCase: (c) => setLive((l) => l && { ...l, completed: l.completed + 1, cases: [...l.cases, c] }),
        onDone: () => void 0,
      });
    } finally {
      setLive(null);
      load().catch(() => void 0);
    }
  }

  async function toggle(id: number) {
    if (open === id) { setOpen(null); setDetail(null); return; }
    setOpen(id);
    setDetail(null);
    setDetail(await getEvalRun(id));
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm">
        <select
          value={suite}
          onChange={(e) => setSuite(e.target.value)}
          disabled={!!live}
          className="rounded-lg border border-card-line bg-card px-2.5 py-1.5 text-ink-soft focus:outline-none focus:ring-2 focus:ring-terracotta/15 disabled:opacity-50"
        >
          {suites.map((s) => <option key={s.key} value={s.key}>{s.key}</option>)}
        </select>
        {selected && (
          <span className="text-xs text-muted">
            {selected.needs_eval_gen ? t("eval.needsJudge") : t("eval.ruleBased")}
          </span>
        )}
        <button
          onClick={run}
          disabled={!!live || !suite}
          className="rounded-lg bg-terracotta px-3.5 py-1.5 font-medium text-white transition-colors hover:bg-terracotta-ink disabled:bg-muted disabled:opacity-50"
        >
          {live ? t("eval.runningBtn") : t("eval.run")}
        </button>
        <span className="ml-auto text-muted">{t("eval.count", { n: runs.length })}</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {live && (
          <div className="border-b border-line bg-paper-raised px-4 py-3 text-sm">
            <div className="flex items-center gap-2">
              <Tag>{live.suite}</Tag>
              <span className="text-ink-soft">
                {t("eval.running", { done: live.completed, total: live.total || "?" })}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1.5">
              {live.cases.map((c) => (
                <span key={c.seq} className="inline-flex items-center gap-1 text-xs" title={c.case}>
                  <span className="max-w-[10rem] truncate text-muted">{c.case}</span>
                  <StatusChip status={c.status} />
                </span>
              ))}
            </div>
          </div>
        )}

        {runs.map((r) => (
          <div key={r.id} className="border-b border-line/70 px-4 py-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Tag>{r.suite}</Tag>
              <StatusChip status={r.status} />
              <span className="text-xs text-ink-soft">
                {r.status === "running"
                  ? t("eval.running", { done: r.completed, total: r.total })
                  : summarize(r.aggregate)}
              </span>
              <span className="ml-auto text-xs text-muted">{r.started_at}</span>
              <button
                className="text-terracotta-ink transition-colors hover:text-terracotta"
                onClick={() => toggle(r.id)}
              >
                {open === r.id ? t("eval.collapse") : t("eval.expand")}
              </button>
            </div>

            {open === r.id && detail && detail.run.id === r.id && (
              <div className="mt-3 space-y-4">
                {r.error && <div className="text-xs text-status-warn-fg">{r.error}</div>}
                <div>
                  <div className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
                    {t("eval.casesTitle")}
                  </div>
                  {detail.results.length === 0 && (
                    <div className="text-xs text-muted">{t("eval.noCases")}</div>
                  )}
                  {detail.results.map((c) => (
                    <div key={c.id} className="mt-1.5 rounded-lg bg-paper-raised p-3 text-xs">
                      <div className="flex items-center gap-2">
                        <StatusChip status={c.status} />
                        <span className="font-medium text-ink">{c.case_name}</span>
                      </div>
                      {c.result && <div className="mt-1.5 text-ink-soft">{summarize(c.result)}</div>}
                      {c.error && <div className="mt-1.5 text-status-warn-fg">{c.error}</div>}
                    </div>
                  ))}
                </div>

                {detail.traces.length > 0 && (
                  <div>
                    <div className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
                      {t("eval.tracesTitle")}
                    </div>
                    {detail.traces.map((tr) => (
                      <div key={tr.id} className="mt-1.5 text-xs">
                        <div className="text-muted">
                          {tr.eval_case} · {tr.stage} · {tr.prompt_tokens ?? "?"}→{tr.completion_tokens ?? "?"} tok · {tr.duration_ms ?? "?"}ms
                        </div>
                        <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-paper-raised p-3 font-sans leading-relaxed text-ink-soft">
                          {tr.output ?? <span className="text-muted">{t("eval.tracePruned")}</span>}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {runs.length === 0 && !live && <div className="p-8 text-muted">{t("eval.empty")}</div>}
      </div>
    </div>
  );
}
