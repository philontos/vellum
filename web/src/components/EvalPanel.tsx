import { useEffect, useState } from "react";
import {
  getEvalRuns, getEvalRun, streamEvalRun,
  type EvalSuite, type EvalRun, type EvalRunDetail, type EvalCaseEvent,
} from "../api/client";
import { useT } from "../i18n";

type Live = { suite: string; total: number; completed: number; cases: EvalCaseEvent[] };

const STATUS_COLOR: Record<string, string> = {
  pass: "bg-green-100 text-green-700",
  fail: "bg-red-100 text-red-700",
  error: "bg-amber-100 text-amber-700",
  scored: "bg-blue-100 text-blue-700",
  running: "bg-gray-100 text-gray-600",
  done: "bg-green-100 text-green-700",
};

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
      <div className="flex items-center gap-2 border-b border-gray-200 p-2 text-sm">
        <select
          value={suite}
          onChange={(e) => setSuite(e.target.value)}
          disabled={!!live}
          className="rounded border px-2 py-1"
        >
          {suites.map((s) => <option key={s.key} value={s.key}>{s.key}</option>)}
        </select>
        {selected && (
          <span className="text-xs text-gray-400">
            {selected.needs_eval_gen ? t("eval.needsJudge") : t("eval.ruleBased")}
          </span>
        )}
        <button
          onClick={run}
          disabled={!!live || !suite}
          className="rounded border px-2 py-1 disabled:opacity-40"
        >
          {live ? t("eval.runningBtn") : t("eval.run")}
        </button>
        <span className="ml-auto text-gray-400">{t("eval.count", { n: runs.length })}</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {live && (
          <div className="border-b border-blue-100 bg-blue-50 px-3 py-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="rounded bg-gray-100 px-1.5 text-xs">{live.suite}</span>
              <span className="text-gray-600">
                {t("eval.running", { done: live.completed, total: live.total || "?" })}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap gap-1">
              {live.cases.map((c) => (
                <span key={c.seq} className={`rounded px-1.5 text-xs ${STATUS_COLOR[c.status] ?? ""}`}
                      title={c.case}>
                  {c.case}: {c.status}
                </span>
              ))}
            </div>
          </div>
        )}

        {runs.map((r) => (
          <div key={r.id} className="border-b border-gray-100 px-3 py-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="rounded bg-gray-100 px-1.5 text-xs">{r.suite}</span>
              <span className={`rounded px-1.5 text-xs ${STATUS_COLOR[r.status] ?? ""}`}>{r.status}</span>
              <span className="text-xs text-gray-500">
                {r.status === "running"
                  ? t("eval.running", { done: r.completed, total: r.total })
                  : summarize(r.aggregate)}
              </span>
              <span className="ml-auto text-xs text-gray-400">{r.started_at}</span>
              <button className="text-blue-600" onClick={() => toggle(r.id)}>
                {open === r.id ? t("eval.collapse") : t("eval.expand")}
              </button>
            </div>

            {open === r.id && detail && detail.run.id === r.id && (
              <div className="mt-2 space-y-3">
                {r.error && <div className="text-xs text-amber-700">{r.error}</div>}
                <div>
                  <div className="text-xs font-semibold text-gray-500">{t("eval.casesTitle")}</div>
                  {detail.results.length === 0 && (
                    <div className="text-xs text-gray-400">{t("eval.noCases")}</div>
                  )}
                  {detail.results.map((c) => (
                    <div key={c.id} className="mt-1 rounded bg-gray-50 p-2 text-xs">
                      <div className="flex items-center gap-2">
                        <span className={`rounded px-1.5 ${STATUS_COLOR[c.status] ?? ""}`}>{c.status}</span>
                        <span className="font-medium">{c.case_name}</span>
                      </div>
                      {c.result && <div className="mt-1 text-gray-600">{summarize(c.result)}</div>}
                      {c.error && <div className="mt-1 text-amber-700">{c.error}</div>}
                    </div>
                  ))}
                </div>

                {detail.traces.length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-gray-500">{t("eval.tracesTitle")}</div>
                    {detail.traces.map((tr) => (
                      <div key={tr.id} className="mt-1 text-xs">
                        <div className="text-gray-500">
                          {tr.eval_case} · {tr.stage} · {tr.prompt_tokens ?? "?"}→{tr.completion_tokens ?? "?"} tok · {tr.duration_ms ?? "?"}ms
                        </div>
                        <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-2">
                          {tr.output ?? <span className="text-gray-400">{t("eval.tracePruned")}</span>}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {runs.length === 0 && !live && <div className="p-4 text-gray-400">{t("eval.empty")}</div>}
      </div>
    </div>
  );
}
