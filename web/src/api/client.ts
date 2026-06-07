import { splitFrames, parseData } from "./sse";

export type Message = { turn: number; role: "user" | "assistant"; content: string };

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

export async function streamChat(message: string, onDelta: (t: string) => void): Promise<void> {
  const r = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok || !r.body) throw new Error(`chat failed: ${r.status}`);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { frames, rest } = splitFrames(buffer);
    buffer = rest;
    for (const frame of frames) {
      const ev = parseData(frame);
      if (ev?.type === "delta") onDelta(ev.text);
      else if (ev?.type === "done") return;
    }
  }
}
