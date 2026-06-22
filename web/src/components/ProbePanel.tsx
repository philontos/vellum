import { useState, type ReactNode } from "react";
import { probe, type ProbeResult } from "../api/client";
import { useT } from "../i18n";

/** Read-only recall inspector. Ask a question, see exactly what the assistant
 * would recall: the query-dependent retrieval (scored hits + below-threshold
 * near-misses + the actual recalled text) and the query-independent durable
 * facts board that rides along every turn. Nothing is persisted. */
export function ProbePanel() {
  const { t } = useT();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<ProbeResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  async function run() {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      setRes(await probe(q));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const facts = (res?.facts ?? []).filter((f) =>
    f.text.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="v-canvas flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") run(); }}
          placeholder={t("probe.placeholder")}
          className="flex-1 rounded-lg border border-line bg-surface px-3 py-1.5 text-ink-soft focus:outline-none focus:ring-2 focus:ring-accent/20"
        />
        <button
          onClick={run}
          disabled={busy}
          className="rounded-lg bg-accent px-3.5 py-1.5 font-medium text-accent-fg transition-colors hover:bg-accent-ink disabled:opacity-60"
        >
          {busy ? t("probe.running") : t("probe.run")}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 text-sm">
        {err && <div className="text-status-warn-fg">{t("probe.error")} {err}</div>}
        {!res && !err && <div className="p-8 text-muted">{t("probe.empty")}</div>}

        {res && (
          <div className="space-y-6">
            <section>
              <SectionLabel>{t("probe.retrievedTitle")}</SectionLabel>
              {res.params && (
                <div className="mb-2 font-mono text-[11px] text-muted">
                  k={res.params.k} · min_sim={res.params.min_sim} · w={res.params.w}
                </div>
              )}

              {res.hits.length === 0 ? (
                <div className="text-xs text-muted">{t("probe.noHits")}</div>
              ) : (
                <div className="space-y-1">
                  {res.hits.map((h, i) => (
                    <div
                      key={i}
                      className={`flex items-center gap-2 text-xs ${h.kept ? "" : "opacity-45"}`}
                    >
                      <span className="w-9 font-mono tabular-nums text-ink-soft">{h.sim.toFixed(2)}</span>
                      <span className="h-1.5 w-24 flex-none overflow-hidden rounded-full bg-well">
                        <span
                          className={`block h-full ${h.kept ? "bg-accent" : "bg-muted"}`}
                          style={{ width: `${Math.max(0, Math.min(1, h.sim)) * 100}%` }}
                        />
                      </span>
                      <span className="text-muted">{h.ref_type ?? "?"}</span>
                      {h.kept && h.window ? (
                        <span className="text-ink-soft">· {t("probe.window", { start: h.window[0], end: h.window[1] })}</span>
                      ) : (
                        <span className="text-muted">· {t("probe.belowThreshold")}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {res.snippets.length > 0 && (
                <div className="mt-3 space-y-2">
                  {res.snippets.map((s, i) => (
                    <div key={i}>
                      <div className="mb-1 font-mono text-[11px] text-muted">
                        {t("probe.window", { start: s.start, end: s.end })}
                      </div>
                      <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-well p-3 font-mono text-[11px] leading-relaxed text-ink-soft">{s.text}</pre>
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section>
              <SectionLabel>{t("probe.alwaysTitle")}</SectionLabel>
              <div className="mb-2 text-xs text-muted">{t("probe.alwaysHint")}</div>
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder={t("probe.factsFilter")}
                className="mb-2 w-full rounded-lg border border-line bg-surface px-2.5 py-1 text-xs text-ink-soft focus:outline-none focus:ring-2 focus:ring-accent/20"
              />
              {facts.length === 0 ? (
                <div className="text-xs text-muted">{t("probe.noFacts")}</div>
              ) : (
                <div className="space-y-1">
                  {facts.map((f) => (
                    <div
                      key={f.id}
                      className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink-soft"
                    >
                      {f.text}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
      {children}
    </div>
  );
}
