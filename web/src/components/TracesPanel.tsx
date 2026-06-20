import { useEffect, useState, type ReactNode } from "react";
import { getTraces, patchTrace, type Trace } from "../api/client";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";
import { backgroundPasses, groupRounds } from "./traces/group";
import { RoundCard } from "./traces/RoundCard";
import { TraceRow } from "./traces/TraceRow";
import { Tag } from "./ui/StatusChip";

type TabKey = "rounds" | "background";

export function TracesPanel() {
  const { t: tr } = useT();
  const blur = usePrivacyBlur();
  const [tab, setTab] = useState<TabKey>("rounds");
  const [rows, setRows] = useState<Trace[]>([]);

  async function load() {
    setRows(await getTraces());
  }
  useEffect(() => { load().catch(() => void 0); }, []);

  async function pin(t: Trace) {
    await patchTrace(t.id, { pinned: !t.pinned });
    load();
  }
  async function note(t: Trace, value: string) {
    await patchTrace(t.id, { note: value });
    load();
  }

  const rounds = groupRounds(rows);
  const passes = backgroundPasses(rows);

  return (
    <div className="v-canvas flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm">
        <div className="flex rounded-lg border border-line bg-surface p-0.5">
          <TabButton active={tab === "rounds"} onClick={() => setTab("rounds")}>
            {tr("traces.tabRounds")}
          </TabButton>
          <TabButton active={tab === "background"} onClick={() => setTab("background")}>
            {tr("traces.tabBackground")}
          </TabButton>
        </div>
        <button
          onClick={() => load()}
          className="rounded-lg border border-line bg-surface px-3 py-1.5 text-ink-soft transition-colors hover:bg-white/5"
        >
          {tr("traces.refresh")}
        </button>
        <span className="ml-auto text-muted">
          {tab === "rounds"
            ? tr("traces.roundCount", { n: rounds.length })
            : tr("traces.passCount", { n: passes.length })}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {tab === "rounds" ? (
          rounds.length > 0 ? (
            rounds.map((r) => (
              <RoundCard key={r.turn ?? "ungrouped"} round={r} onPin={pin} onNote={note} blur={blur} />
            ))
          ) : (
            <div className="p-8 text-muted">{tr("traces.empty")}</div>
          )
        ) : passes.length > 0 ? (
          passes.map((p) => (
            <div key={p.id} className="border-b border-line/70 px-4 py-3">
              <TraceRow
                trace={p}
                onPin={pin}
                onNote={note}
                blur={blur}
                badge={<SpanBadge from={p.from} to={p.to} />}
              />
            </div>
          ))
        ) : (
          <div className="p-8 text-muted">{tr("traces.emptyBackground")}</div>
        )}
      </div>
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
