import { splitFrames, parseData, parseEvalFrame, type ToolEvent } from "./sse";
import type { ActivityItem } from "./activity";

/**
 * Race a promise against a deadline. If it doesn't settle within `ms`, abort the
 * request and reject — so a silently-dead connection (e.g. a dropped SSH tunnel
 * that sends no FIN/RST) can't leave us hanging forever. Guards two phases: the
 * `connect` (waiting for response headers) and each mid-stream `read` (no data).
 */
function withDeadline<T>(p: Promise<T>, ms: number, ctrl: AbortController, what: string): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const deadline = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      ctrl.abort();
      reject(new Error(`${what} timed out after ${ms}ms`));
    }, ms);
  });
  return Promise.race([p, deadline]).finally(() => clearTimeout(timer));
}

export type Message = {
  turn: number;
  role: "user" | "assistant";
  content: string;
  created_at?: string; // ISO/sqlite datetime; present from /history, stamped client-side for live turns
  reasoning?: string; // live-only: the model's thinking for this turn (not persisted; see Traces)
  activity?: ActivityItem[]; // live-only: tool calls (e.g. web_search) made this turn
  failed?: boolean; // live-only: this turn's stream failed (timeout/network) — the UI offers a retry
};

/**
 * Load chat history. Without `before` it returns the recent tail (page load);
 * with `before` it returns the window of messages immediately older than that
 * turn — the chat view's scroll-up page.
 */
export async function getHistory(opts: { limit?: number; before?: number } = {}): Promise<Message[]> {
  const q = new URLSearchParams({ limit: String(opts.limit ?? 200) });
  if (opts.before !== undefined) q.set("before", String(opts.before));
  const r = await fetch(`/history?${q}`);
  if (!r.ok) throw new Error(`history failed: ${r.status}`);
  return (await r.json()).messages;
}

/**
 * Soft-delete one history turn (a stray retry or debug line). The server keeps
 * the row but drops it from every model-facing read path; reversible at the db
 * level. Idempotent — deleting an unknown/already-gone turn still resolves ok.
 */
export async function deleteMessage(turn: number): Promise<void> {
  const r = await fetch(`/history/${turn}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete failed: ${r.status}`);
}

/** One diary timeline card — a background summary of a conversation span. */
export type DiaryCard = {
  id: number;
  start_turn: number;
  end_turn: number;
  content: string;
  created_at: string;
};

/** List diary cards newest-first. `before` is a card id (keyset paging). */
export async function getDiary(before?: number, limit = 20): Promise<DiaryCard[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (before !== undefined) q.set("before", String(before));
  const r = await fetch(`/diary?${q}`);
  if (!r.ok) throw new Error(`diary failed: ${r.status}`);
  return (await r.json()).cards;
}

/** Expand one diary card into the full message span it digests. */
export async function getDiaryMessages(id: number): Promise<{ summary: DiaryCard; messages: Message[] }> {
  const r = await fetch(`/diary/${id}`);
  if (!r.ok) throw new Error(`diary detail failed: ${r.status}`);
  return r.json();
}

/**
 * POST /chat and stream the assistant reply. Calls onDelta for each text chunk.
 * Resolves when the stream completes ([DONE]).
 */
/** Display metadata for one sub-dimension. `poles` ([low@0, high@100]) marks it
 * bipolar — the UI renders a centered diverging bar; its absence means unipolar. */
export type SubDimMeta = { key: string; name: string; poles?: [string, string] };
export type TraitMeta = {
  name: string; label: string; sort_by_score: boolean; sub_dimensions: SubDimMeta[];
};
export type TraitDim = {
  dimension: string;
  content_json: Record<string, { score?: number; confidence?: number; evidence?: string }>;
  sample_count: number;
  updated_at: string;
  history: { taken_at: string; content_json: Record<string, { score?: number }> }[];
  meta: TraitMeta | null;
};
export type Fact = { id: number; text: string; status: string; source_turn: number | null };
export type ModelView = { dossier: string; facts: Fact[]; traits: TraitDim[] };
export type Trace = {
  id: number; turn: number | null; stage: string; model: string | null;
  prompt: string | null; output: string | null; reasoning: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null; duration_ms: number | null; pinned: number;
  note: string | null; created_at: string;
  params: string | null; // JSON blob; background passes carry {from,to} covered-span
};

export async function getModel(): Promise<ModelView> {
  const r = await fetch("/inspect/model");
  if (!r.ok) throw new Error(`model failed: ${r.status}`);
  return r.json();
}

export async function getTraces(stage?: string, limit = 100): Promise<Trace[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (stage) q.set("stage", stage);
  const r = await fetch(`/inspect/traces?${q}`);
  if (!r.ok) throw new Error(`traces failed: ${r.status}`);
  return (await r.json()).traces;
}

export async function patchTrace(id: number, patch: { pinned?: boolean; note?: string }): Promise<void> {
  const r = await fetch(`/inspect/traces/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`patch failed: ${r.status}`);
}

// --- evals ---------------------------------------------------------------

export type EvalSuite = { key: string; needs_eval_gen: boolean };
export type EvalRun = {
  id: number; suite: string; status: "running" | "done" | "error";
  model: string | null; eval_model: string | null;
  total: number; completed: number;
  aggregate: Record<string, unknown> | null; error: string | null;
  started_at: string; finished_at: string | null;
};
export type EvalResult = {
  id: number; run_id: number; seq: number; case_name: string;
  status: "pass" | "fail" | "scored" | "error";
  result: Record<string, unknown> | null; error: string | null; created_at: string;
};
export type EvalTrace = Trace & { eval_case: string | null };
export type EvalRunDetail = { run: EvalRun; results: EvalResult[]; traces: EvalTrace[] };

export async function getEvalRuns(limit = 50): Promise<{ runs: EvalRun[]; suites: EvalSuite[] }> {
  const r = await fetch(`/inspect/evals?limit=${limit}`);
  if (!r.ok) throw new Error(`evals failed: ${r.status}`);
  return r.json();
}

export async function getEvalRun(id: number): Promise<EvalRunDetail> {
  const r = await fetch(`/inspect/evals/${id}`);
  if (!r.ok) throw new Error(`eval run failed: ${r.status}`);
  return r.json();
}

export type EvalRunMeta = { id: number; suite: string; total: number; needs_eval_gen: boolean };
export type EvalCaseEvent = {
  seq: number; case: string; status: EvalResult["status"];
  result: Record<string, unknown> | null; error: string | null;
};
export type EvalDoneEvent = { run_id: number; status: string; aggregate: Record<string, unknown> | null; error?: string };

/** POST /inspect/evals/run and stream the run. Resolves when the stream ends. */
export async function streamEvalRun(
  suite: string,
  cb: { onRun?: (m: EvalRunMeta) => void; onCase?: (c: EvalCaseEvent) => void; onDone?: (d: EvalDoneEvent) => void },
  opts: { idleTimeoutMs?: number } = {},
): Promise<void> {
  const idleMs = opts.idleTimeoutMs ?? 120_000;
  const ctrl = new AbortController();
  const r = await fetch(`/inspect/evals/run?suite=${encodeURIComponent(suite)}`, {
    method: "POST",
    signal: ctrl.signal,
  });
  if (!r.ok || !r.body) throw new Error(`eval run failed: ${r.status}`);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await withDeadline(reader.read(), idleMs, ctrl, "stream");
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { frames, rest } = splitFrames(buffer);
      buffer = rest;
      for (const frame of frames) {
        const ev = parseEvalFrame(frame);
        if (!ev) continue;
        if (ev.kind === "run") cb.onRun?.(ev.data as unknown as EvalRunMeta);
        else if (ev.kind === "case") cb.onCase?.(ev.data as unknown as EvalCaseEvent);
        else if (ev.kind === "done") cb.onDone?.(ev.data as unknown as EvalDoneEvent);
        else if (ev.kind === "end") return;
      }
    }
  } finally {
    ctrl.abort();
  }
}

// --- probe (read-only recall inspector) ----------------------------------

/** One turn the recall pipeline would hydrate into context. */
export type ProbeRow = { turn: number; role: "user" | "assistant"; content: string };

/** One vector hit for a probe query. `kept` = passed the similarity threshold
 * (so it shaped a recalled window); below-threshold near-misses come back too,
 * with kept=false, so you can see what *almost* surfaced. For kept hits, `rows`
 * is the window this hit would pull (the anchor turn + its neighbours); a summary
 * hit also carries its `digest` (the text production never re-emits — it recalls
 * the marked range's raw turns instead). */
export type ProbeHit = {
  sim: number;
  kept: boolean;
  ref_type: "message" | "summary" | null;
  anchor_turn: number | null;
  window: [number, number] | null;
  digest: string | null;
  rows: ProbeRow[];
};
export type ProbeSnippet = { start: number; end: number; text: string };
export type ProbeResult = {
  query: string;
  params: { k: number; min_sim: number; w: number } | null;
  hits: ProbeHit[];
  snippets: ProbeSnippet[];
  facts: Fact[];
};

/** GET /inspect/probe — read-only: what the recall pipeline surfaces for `q`,
 * plus the always-in-context durable facts. Persists nothing. */
export async function probe(q: string): Promise<ProbeResult> {
  const r = await fetch(`/inspect/probe?q=${encodeURIComponent(q)}`);
  if (!r.ok) throw new Error(`probe failed: ${r.status}`);
  return r.json();
}

export type StreamHandlers = {
  onDelta: (t: string) => void;
  onReasoning?: (t: string) => void;
  onTool?: (ev: ToolEvent) => void;
};

export async function streamChat(
  message: string,
  handlers: StreamHandlers,
  opts: { idleTimeoutMs?: number; connectTimeoutMs?: number; signal?: AbortSignal } = {},
): Promise<void> {
  const idleMs = opts.idleTimeoutMs ?? 90_000;
  // The connect phase has its own (shorter) deadline: a half-dead tunnel never
  // returns response headers, and the idle timeout above only guards reads that
  // happen *after* fetch() resolves — so without this the request hangs forever.
  const connectMs = opts.connectTimeoutMs ?? 12_000;
  const ctrl = new AbortController();
  // Let the caller stop an in-flight stream: their abort funnels into ours so a
  // manual stop, a connect timeout, and an idle timeout all cancel the one fetch.
  if (opts.signal) {
    if (opts.signal.aborted) ctrl.abort();
    else opts.signal.addEventListener("abort", () => ctrl.abort(), { once: true });
  }
  const r = await withDeadline(
    fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal: ctrl.signal,
    }),
    connectMs,
    ctrl,
    "connection",
  );
  if (!r.ok || !r.body) throw new Error(`chat failed: ${r.status}`);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await withDeadline(reader.read(), idleMs, ctrl, "stream");
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { frames, rest } = splitFrames(buffer);
      buffer = rest;
      for (const frame of frames) {
        const ev = parseData(frame);
        if (ev?.type === "delta") handlers.onDelta(ev.text);
        else if (ev?.type === "reasoning") handlers.onReasoning?.(ev.text);
        else if (ev?.type === "tool") handlers.onTool?.(ev.tool);
        else if (ev?.type === "error") throw new Error(ev.message);
        else if (ev?.type === "done") return;
      }
    }
  } finally {
    ctrl.abort();
  }
}
