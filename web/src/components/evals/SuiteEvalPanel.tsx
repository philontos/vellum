import { useEffect, useState } from "react";

import {
  getEvalRun,
  getEvalRuns,
  streamEvalRun,
  type EvalRun,
  type EvalRunDetail,
  type EvalSuite,
} from "../../api/client";
import { useT } from "../../i18n";
import { StatusChip, Tag } from "../ui/StatusChip";


type Progress = { done: number; total: number };


export function SuiteEvalPanel() {
  const [suites, setSuites] = useState<EvalSuite[]>([]);
  const [runs, setRuns] = useState<EvalRun[]>([]);
  const [selectedSuite, setSelectedSuite] = useState("inquiry");
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const next = await getEvalRuns();
      setSuites(next.suites);
      setRuns(next.runs);
      if (!next.suites.some((suite) => suite.key === selectedSuite)) {
        setSelectedSuite(next.suites[0]?.key ?? "");
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : String(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  async function run() {
    if (!selectedSuite || running) return;
    setRunning(true);
    setError("");
    setProgress({ done: 0, total: 0 });
    try {
      await streamEvalRun(selectedSuite, {
        onRun: (meta) => setProgress({ done: 0, total: meta.total }),
        onCase: () => setProgress((current) => ({
          done: (current?.done ?? 0) + 1,
          total: current?.total ?? 0,
        })),
      });
      await load();
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : String(runError));
    } finally {
      setRunning(false);
      setProgress(null);
    }
  }

  async function open(runId: number) {
    try {
      setDetail(detail?.run.id === runId ? null : await getEvalRun(runId));
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : String(detailError));
    }
  }

  return (
    <SuiteEvalPanelView
      suites={suites}
      runs={runs}
      selectedSuite={selectedSuite}
      running={running}
      progress={progress}
      detail={detail}
      loading={loading}
      error={error}
      onSuiteChange={setSelectedSuite}
      onRun={() => void run()}
      onRefresh={() => void load()}
      onOpen={(id) => void open(id)}
    />
  );
}


export function SuiteEvalPanelView({
  suites,
  runs,
  selectedSuite,
  running,
  progress,
  detail,
  loading,
  error,
  onSuiteChange,
  onRun,
  onRefresh,
  onOpen,
}: {
  suites: EvalSuite[];
  runs: EvalRun[];
  selectedSuite: string;
  running: boolean;
  progress: Progress | null;
  detail?: EvalRunDetail | null;
  loading: boolean;
  error: string;
  onSuiteChange: (suite: string) => void;
  onRun: () => void;
  onRefresh: () => void;
  onOpen?: (runId: number) => void;
}) {
  const { t } = useT();
  const selected = suites.find((suite) => suite.key === selectedSuite);
  return (
    <div className="v-canvas h-full overflow-y-auto p-4 sm:p-6">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap items-start gap-3">
          <div className="mr-auto">
            <h2 className="font-serif text-xl text-ink">{t("eval.suiteTitle")}</h2>
            <p className="mt-1 text-sm text-muted">{t("eval.suiteSubtitle")}</p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink-soft"
          >
            {t("eval.refresh")}
          </button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {suites.map((suite) => (
            <button
              key={suite.key}
              type="button"
              onClick={() => onSuiteChange(suite.key)}
              className={`rounded-lg border px-3 py-2 text-sm ${
                selectedSuite === suite.key
                  ? "border-accent/50 bg-accent/15 text-accent"
                  : "border-line bg-surface text-ink-soft"
              }`}
            >
              <span>{suite.key}</span>
              <span className="ml-2 text-[10px] opacity-70">
                {suite.needs_eval_gen ? t("eval.needsJudge") : t("eval.ruleBased")}
              </span>
            </button>
          ))}
          <button
            type="button"
            onClick={onRun}
            disabled={!selected || running}
            className="rounded-lg bg-accent px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            {running
              ? t("eval.running", {
                  done: progress?.done ?? 0, total: progress?.total ?? 0,
                })
              : t("eval.run")}
          </button>
        </div>

        {error && <div role="alert" className="mt-4 text-sm text-status-fail-fg">{error}</div>}
        {loading && runs.length === 0 ? (
          <div className="mt-6 text-sm text-muted">{t("eval.loading")}</div>
        ) : runs.length === 0 ? (
          <div className="mt-6 text-sm text-muted">{t("eval.empty")}</div>
        ) : (
          <div className="mt-6 space-y-3">
            {runs.map((run) => (
              <section key={run.id} className="rounded-xl border border-line bg-surface p-4">
                <button
                  type="button"
                  onClick={() => onOpen?.(run.id)}
                  className="flex w-full flex-wrap items-center gap-2 text-left"
                >
                  <span className="font-mono text-xs text-muted">#{run.id}</span>
                  <Tag>{run.suite}</Tag>
                  <StatusChip status={run.status} />
                  <span className="text-xs text-muted">{run.completed}/{run.total}</span>
                  <span className="ml-auto text-xs text-muted">{run.model ?? "—"}</span>
                </button>
                {run.aggregate && <Aggregate value={run.aggregate} />}
                {detail?.run.id === run.id && (
                  <div className="mt-4 border-t border-line pt-3">
                    <div className="text-[10px] uppercase tracking-[0.12em] text-muted">
                      {t("eval.casesTitle")}
                    </div>
                    <div className="mt-2 space-y-1.5">
                      {detail.results.map((result) => (
                        <details key={result.id} className="rounded-lg border border-line bg-canvas px-3 py-2">
                          <summary className="flex cursor-pointer list-none items-center gap-2 text-xs">
                            <StatusChip status={result.status} />
                            <span className="text-ink-soft">{result.case_name}</span>
                            {result.error && <span className="text-status-fail-fg">{result.error}</span>}
                          </summary>
                          {result.result && (
                            <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md bg-surface p-2 font-mono text-[11px] text-muted">
                              {JSON.stringify(result.result, null, 2)}
                            </pre>
                          )}
                        </details>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


function Aggregate({ value }: { value: Record<string, unknown> }) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {Object.entries(value).map(([key, metric]) => (
        <span key={key} className="rounded-md bg-canvas px-2 py-1 text-xs text-muted">
          {key.replace(/_/g, " ")}: <strong className="font-medium text-ink-soft">{String(metric)}</strong>
        </span>
      ))}
    </div>
  );
}
