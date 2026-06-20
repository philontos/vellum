import { splitFrames, parseData, parseEvalFrame } from "./sse";

/**
 * Read the next chunk, but reject if nothing arrives within `idleMs` — and abort
 * the request so a silently-dead connection (e.g. a dropped SSH tunnel that
 * sends no FIN/RST) can't leave the reader hanging forever.
 */
async function readWithTimeout<T>(
  reader: { read: () => Promise<T> },
  idleMs: number,
  ctrl: AbortController,
): Promise<T> {
  let timer: ReturnType<typeof setTimeout>;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      ctrl.abort();
      reject(new Error(`stream timed out after ${idleMs}ms with no data`));
    }, idleMs);
  });
  try {
    return await Promise.race([reader.read(), timeout]);
  } finally {
    clearTimeout(timer!);
  }
}

export type Message = {
  turn: number;
  role: "user" | "assistant";
  content: string;
  created_at?: string; // ISO/sqlite datetime; present from /history, stamped client-side for live turns
};

export async function getHistory(limit = 200): Promise<Message[]> {
  const r = await fetch(`/history?limit=${limit}`);
  if (!r.ok) throw new Error(`history failed: ${r.status}`);
  return (await r.json()).messages;
}

/**
 * POST /chat and stream the assistant reply. Calls onDelta for each text chunk.
 * Resolves when the stream completes ([DONE]).
 */
export type TraitDim = {
  dimension: string;
  content_json: Record<string, { score?: number; confidence?: number; evidence?: string }>;
  sample_count: number;
  updated_at: string;
  history: { taken_at: string; content_json: Record<string, { score?: number }> }[];
};
export type Fact = { id: number; text: string; status: string; source_turn: number | null };
export type ModelView = { dossier: string; facts: Fact[]; traits: TraitDim[] };
export type Trace = {
  id: number; turn: number | null; stage: string; model: string | null;
  prompt: string | null; output: string | null; reasoning: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null; duration_ms: number | null; pinned: number;
  note: string | null; created_at: string;
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
      const { value, done } = await readWithTimeout(reader, idleMs, ctrl);
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

export async function streamChat(
  message: string,
  onDelta: (t: string) => void,
  opts: { idleTimeoutMs?: number } = {},
): Promise<void> {
  const idleMs = opts.idleTimeoutMs ?? 90_000;
  const ctrl = new AbortController();
  const r = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal: ctrl.signal,
  });
  if (!r.ok || !r.body) throw new Error(`chat failed: ${r.status}`);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await readWithTimeout(reader, idleMs, ctrl);
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const { frames, rest } = splitFrames(buffer);
      buffer = rest;
      for (const frame of frames) {
        const ev = parseData(frame);
        if (ev?.type === "delta") onDelta(ev.text);
        else if (ev?.type === "error") throw new Error(ev.message);
        else if (ev?.type === "done") return;
      }
    }
  } finally {
    ctrl.abort();
  }
}
