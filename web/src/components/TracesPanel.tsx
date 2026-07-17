import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { getTraces, patchTrace, type TraceSummary } from "../api/client";
import { useT } from "../i18n";
import { backgroundPasses, groupRounds } from "./traces/group";
import { RoundCard } from "./traces/RoundCard";
import { TraceRow } from "./traces/TraceRow";
import { Tag } from "./ui/StatusChip";

export type TabKey = "rounds" | "background";

const TRACE_REFRESH_MS = 10_000;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function TracesPanel() {
  const [tab, setTab] = useState<TabKey>("rounds");
  const [rows, setRows] = useState<TraceSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const mounted = useRef(true);

  const load = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (mounted.current) {
      setLoading(true);
      setError("");
    }
    try {
      const next = await getTraces();
      if (mounted.current) setRows(next);
    } catch (loadError: unknown) {
      if (mounted.current) setError(errorMessage(loadError));
    } finally {
      inFlight.current = false;
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void load();
    const timer = window.setInterval(() => void load(), TRACE_REFRESH_MS);
    const refreshOnFocus = () => void load();
    window.addEventListener("focus", refreshOnFocus);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshOnFocus);
    };
  }, [load]);

  async function pin(trace: TraceSummary) {
    try {
      await patchTrace(trace.id, { pinned: !trace.pinned });
      setRows((current) => current.map((row) => (
        row.id === trace.id ? { ...row, pinned: trace.pinned ? 0 : 1 } : row
      )));
    } catch (patchError: unknown) {
      setError(errorMessage(patchError));
    }
  }
  async function note(trace: TraceSummary, value: string) {
    try {
      await patchTrace(trace.id, { note: value });
      setRows((current) => current.map((row) => (
        row.id === trace.id ? { ...row, note: value } : row
      )));
    } catch (patchError: unknown) {
      setError(errorMessage(patchError));
    }
  }

  return (
    <TracesPanelView
      rows={rows}
      tab={tab}
      loading={loading}
      error={error}
      onTabChange={setTab}
      onRefresh={() => void load()}
      onPin={pin}
      onNote={note}
    />
  );
}

export function TracesPanelView({
  rows,
  tab,
  loading,
  error,
  onTabChange,
  onRefresh,
  onPin,
  onNote,
}: {
  rows: TraceSummary[];
  tab: TabKey;
  loading: boolean;
  error: string;
  onTabChange: (tab: TabKey) => void;
  onRefresh: () => void;
  onPin: (trace: TraceSummary) => void;
  onNote: (trace: TraceSummary, value: string) => void;
}) {
  const { t: tr } = useT();
  const rounds = groupRounds(rows);
  const passes = backgroundPasses(rows);
  const firstLoad = loading && rows.length === 0;
  const firstLoadFailed = Boolean(error) && rows.length === 0;

  return (
    <div className="v-canvas flex h-full flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-3 text-sm sm:px-4">
        <div className="flex rounded-lg border border-line bg-surface p-0.5">
          <TabButton active={tab === "rounds"} onClick={() => onTabChange("rounds")}>
            {tr("traces.tabRounds")}
          </TabButton>
          <TabButton active={tab === "background"} onClick={() => onTabChange("background")}>
            {tr("traces.tabBackground")}
          </TabButton>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="rounded-lg border border-line bg-surface px-3 py-1.5 text-ink-soft transition-colors hover:bg-white/5 disabled:cursor-wait disabled:opacity-60"
        >
          {tr("traces.refresh")}
        </button>
        <span className="ml-auto text-xs text-muted sm:text-sm">
          {tab === "rounds"
            ? rounds.length === 1
              ? tr("traces.roundCountOne")
              : tr("traces.roundCount", { n: rounds.length })
            : passes.length === 1
              ? tr("traces.passCountOne")
              : tr("traces.passCount", { n: passes.length })}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {error && rows.length > 0 && (
          <LoadError error={error} onRetry={onRefresh} compact />
        )}
        {firstLoad ? (
          <div className="p-4 text-muted sm:p-8">{tr("traces.loading")}</div>
        ) : firstLoadFailed ? (
          <LoadError error={error} onRetry={onRefresh} />
        ) : tab === "rounds" ? (
          rounds.length > 0 ? (
            rounds.map((r) => (
              <RoundCard key={r.turn ?? "ungrouped"} round={r} onPin={onPin} onNote={onNote} />
            ))
          ) : (
            <div className="p-4 text-muted sm:p-8">{tr("traces.empty")}</div>
          )
        ) : passes.length > 0 ? (
          passes.map((p) => (
            <div key={p.id} className="border-b border-line/70 px-3 py-3 sm:px-4">
              <TraceRow
                trace={p}
                onPin={onPin}
                onNote={onNote}
                badge={<SpanBadge from={p.from} to={p.to} />}
              />
            </div>
          ))
        ) : (
          <div className="p-4 text-muted sm:p-8">{tr("traces.emptyBackground")}</div>
        )}
      </div>
    </div>
  );
}

function LoadError({
  error,
  onRetry,
  compact = false,
}: {
  error: string;
  onRetry: () => void;
  compact?: boolean;
}) {
  const { t: tr } = useT();
  return (
    <div
      role="alert"
      className={`${compact ? "mx-3 mt-3 sm:mx-4" : "m-4 sm:m-8"} rounded-lg border border-status-fail-fg/30 bg-status-fail-bg px-3 py-3 text-status-fail-fg`}
    >
      <div>{tr("traces.loadFailed")}</div>
      <div className="mt-1 font-mono text-[11px] opacity-80">{error}</div>
      <button
        type="button"
        onClick={onRetry}
        className="mt-2 rounded-md border border-current/30 px-2.5 py-1 text-xs transition-colors hover:bg-white/5"
      >
        {tr("traces.retry")}
      </button>
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1 text-sm transition-colors ${
        active ? "bg-accent/15 text-accent" : "text-muted hover:text-ink-soft"
      }`}
    >
      {children}
    </button>
  );
}

/** "covers turns from–to (N)" — signals a pass is a roll-up over many turns, not one round. */
function SpanBadge({ from, to }: { from: number | null; to: number | null }) {
  const { t: tr } = useT();
  if (from === null || to === null) return null;
  return <Tag>{tr("traces.span", { from, to, n: to - from + 1 })}</Tag>;
}
