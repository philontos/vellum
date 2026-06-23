import { useState, type ReactNode } from "react";
import { probe, type ProbeHit, type ProbeResult, type ProbeRow } from "../api/client";
import { useT } from "../i18n";
import { approxTokens, charCount } from "../util/tokens";

/** Read-only recall inspector. Ask a question and walk the recall pipeline
 * end to end: (1) the scored embedding hits + the threshold gate, (2) each
 * passing hit's own window — a turn match highlights the matched turn among its
 * neighbours, a summary match shows its digest then the raw turns it recalls,
 * (3) those windows merged & deduped exactly as the model receives them, and
 * (4) the query-independent durable facts that ride along every turn. Nothing
 * is persisted. */
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

  const kept = (res?.hits ?? []).filter((h) => h.kept);
  const mergedText = (res?.snippets ?? []).map((s) => s.text).join("\n---\n");
  const factsText = (res?.facts ?? []).map((f) => `- ${f.text}`).join("\n");
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
            {res.params && (
              <>
                {/* Stage 1 — retrieved: scored hits + the threshold gate */}
                <section>
                  <SectionLabel>{t("probe.retrievedTitle")}</SectionLabel>
                  <div className="mb-1.5 font-mono text-[11px] text-muted">
                    k={res.params.k} · min_sim={res.params.min_sim} · w={res.params.w}
                  </div>
                  <div className="mb-2 text-xs text-muted">{t("probe.retrievedHint")}</div>
                  {res.hits.length === 0 ? (
                    <div className="text-xs text-muted">{t("probe.noHits")}</div>
                  ) : (
                    <div className="space-y-1">
                      {res.hits.map((h, i) => (
                        <div key={i} className={`flex items-center gap-2 text-xs ${h.kept ? "" : "opacity-45"}`}>
                          <span className="w-9 font-mono tabular-nums text-ink-soft">{h.sim.toFixed(2)}</span>
                          <span className="h-1.5 w-24 flex-none overflow-hidden rounded-full bg-well">
                            <span
                              className={`block h-full ${h.kept ? "bg-accent" : "bg-muted"}`}
                              style={{ width: `${Math.max(0, Math.min(1, h.sim)) * 100}%` }}
                            />
                          </span>
                          <TypeBadge refType={h.ref_type} />
                          {h.kept && h.window ? (
                            <span className="text-ink-soft">· {t("probe.window", { start: h.window[0], end: h.window[1] })}</span>
                          ) : (
                            <span className="text-muted">· {t("probe.belowThreshold")}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                {/* Stage 2 — each passing hit's own window (cards folded; expand to highlight) */}
                <section>
                  <SectionLabel>{t("probe.windowsTitle")}</SectionLabel>
                  <div className="mb-2 text-xs text-muted">{t("probe.windowsHint")}</div>
                  {kept.length === 0 ? (
                    <div className="text-xs text-muted">{t("probe.noWindows")}</div>
                  ) : (
                    <div className="space-y-1.5">
                      {kept.map((h, i) => <HitCard key={i} hit={h} />)}
                    </div>
                  )}
                </section>

                {/* Stage 3 — merged & sent to the model (folded) */}
                <Collapsible title={t("probe.mergedTitle")} stat={mergedText}>
                  <div className="mb-2 text-xs text-muted">{t("probe.mergedHint")}</div>
                  {res.snippets.length === 0 ? (
                    <div className="text-xs text-muted">{t("probe.noMerged")}</div>
                  ) : (
                    <div className="space-y-2">
                      {res.snippets.map((s, i) => (
                        <div key={i}>
                          <div className="mb-1 flex items-center gap-2 font-mono text-[11px] text-muted">
                            <span>{t("probe.window", { start: s.start, end: s.end })}</span>
                            <span>·</span>
                            <Count text={s.text} />
                          </div>
                          <pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-well p-3 font-mono text-[11px] leading-relaxed text-ink-soft">{s.text}</pre>
                        </div>
                      ))}
                    </div>
                  )}
                </Collapsible>
              </>
            )}

            {/* Stage 4 — always in context: the durable facts board */}
            <section>
              <div className="mb-1.5 flex items-center gap-2">
                <SectionLabel>{t("probe.alwaysTitle")}</SectionLabel>
                {factsText && <Count text={factsText} />}
              </div>
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
                    <div key={f.id} className="rounded-lg border border-line bg-surface px-3 py-1.5 text-xs text-ink-soft">
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

/** One passing hit, folded to a header line; expand to see the window it pulls.
 * A turn match highlights its anchor among the neighbours; a summary match leads
 * with its digest, then the raw turns actually recalled. */
function HitCard({ hit }: { hit: ProbeHit }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  const isSummary = hit.ref_type === "summary";
  const recalledText = hit.rows.map((r) => `${r.role}: ${r.content}`).join("\n");

  return (
    <div className="rounded-lg border border-line bg-surface">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs"
      >
        <Caret open={open} />
        <span className="w-9 font-mono tabular-nums text-ink-soft">{hit.sim.toFixed(2)}</span>
        <TypeBadge refType={hit.ref_type} />
        {hit.window && (
          <span className="text-muted">{t("probe.window", { start: hit.window[0], end: hit.window[1] })}</span>
        )}
        <span className="ml-auto flex items-center gap-2 text-muted">
          <Count text={recalledText} />
          <span className="text-[11px]">{open ? t("probe.collapse") : t("probe.expand")}</span>
        </span>
      </button>
      {open && (
        <div className="border-t border-line px-3 py-2">
          {isSummary ? <SummaryBody hit={hit} /> : (
            <div className="space-y-1">
              {hit.rows.map((r) => (
                <TurnRow key={r.turn} row={r} anchor={r.turn === hit.anchor_turn} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Summary hit: the digest (lost on the model-facing path) up top, the turns it
 * marks, then the raw turns production actually recalls for the marked range. */
function SummaryBody({ hit }: { hit: ProbeHit }) {
  const { t } = useT();
  return (
    <div className="space-y-2">
      <div className="rounded-md border border-gold/40 bg-gold/5 px-3 py-2">
        <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
          {t("probe.digestLabel")}
          {hit.window && <> · {t("probe.markedRange", { start: hit.window[0], end: hit.window[1] })}</>}
        </div>
        <div className="text-[12px] leading-relaxed text-ink-soft">{hit.digest}</div>
        <div className="mt-1.5 text-[10px] leading-relaxed text-muted">{t("probe.digestNote")}</div>
      </div>
      <div className="text-[10px] font-medium uppercase tracking-[0.12em] text-muted">
        {t("probe.recalledTurns")}
      </div>
      <div className="space-y-1">
        {hit.rows.map((r) => <TurnRow key={r.turn} row={r} anchor={false} />)}
      </div>
    </div>
  );
}

/** One recalled turn. `anchor` = the matched turn of a turn-hit, highlighted. */
function TurnRow({ row, anchor }: { row: ProbeRow; anchor: boolean }) {
  const { t } = useT();
  return (
    <div className={`flex gap-2 rounded px-2 py-1 ${anchor ? "bg-accent/10 ring-1 ring-accent/30" : ""}`}>
      <span className="w-12 flex-none font-mono text-[10px] leading-relaxed text-muted">
        #{row.turn} {row.role === "user" ? "U" : "A"}
      </span>
      <span className="min-w-0 flex-1 whitespace-pre-wrap text-[12px] leading-relaxed text-ink-soft">
        {row.content}
      </span>
      {anchor && (
        <span className="flex-none self-start rounded bg-accent px-1.5 py-0.5 text-[9px] font-medium text-accent-fg">
          {t("probe.anchorTag")}
        </span>
      )}
    </div>
  );
}

/** A collapsible section that shows a char/token count in its header even when
 * folded — so the cost of what's inside is visible at a glance. */
function Collapsible({ title, stat, children }: { title: string; stat: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <section>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 text-left"
      >
        <Caret open={open} />
        <SectionLabel>{title}</SectionLabel>
        {stat && <span className="ml-auto"><Count text={stat} /></span>}
      </button>
      {open && <div className="mt-2">{children}</div>}
    </section>
  );
}

function TypeBadge({ refType }: { refType: ProbeHit["ref_type"] }) {
  const { t } = useT();
  const label = refType === "summary" ? t("probe.typeSummary")
    : refType === "message" ? t("probe.typeMessage") : "?";
  return <span className="rounded bg-well px-1.5 py-0.5 text-[10px] text-muted">{label}</span>;
}

function Count({ text }: { text: string }) {
  const { t } = useT();
  return (
    <span className="font-mono text-[11px] text-muted">
      {t("probe.count", { chars: charCount(text), tokens: approxTokens(text) })}
    </span>
  );
}

function Caret({ open }: { open: boolean }) {
  return (
    <span className={`inline-block flex-none text-[9px] text-muted transition-transform ${open ? "rotate-90" : ""}`} aria-hidden>
      ▶
    </span>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
      {children}
    </div>
  );
}
