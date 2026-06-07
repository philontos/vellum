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
