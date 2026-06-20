export type SSEEvent =
  | { type: "delta"; text: string }
  | { type: "error"; message: string }
  | { type: "done" };

/** Split a buffer into complete `\n\n`-terminated SSE frames + leftover. */
export function splitFrames(buffer: string): { frames: string[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  return { frames: parts, rest };
}

/** Parse one SSE frame's `data:` line. Returns null for comments / malformed. */
export function parseData(frame: string): SSEEvent | null {
  const line = frame.split("\n").find((l) => l.startsWith("data:"));
  if (!line) return null;
  const payload = line.slice(5).trim();
  if (payload === "[DONE]") return { type: "done" };
  try {
    const obj = JSON.parse(payload);
    if (typeof obj.delta === "string") return { type: "delta", text: obj.delta };
    if (typeof obj.error === "string") return { type: "error", message: obj.error };
    return null;
  } catch {
    return null;
  }
}

/** Eval-run stream frames: `{run|case|done}` payloads, or `[DONE]` to end. */
export type EvalFrame =
  | { kind: "run"; data: Record<string, unknown> }
  | { kind: "case"; data: Record<string, unknown> }
  | { kind: "done"; data: Record<string, unknown> }
  | { kind: "end" };

/** Parse one eval-run SSE frame's `data:` line. Returns null for comments / malformed. */
export function parseEvalFrame(frame: string): EvalFrame | null {
  const line = frame.split("\n").find((l) => l.startsWith("data:"));
  if (!line) return null;
  const payload = line.slice(5).trim();
  if (payload === "[DONE]") return { kind: "end" };
  try {
    const obj = JSON.parse(payload);
    if (obj.run) return { kind: "run", data: obj.run };
    if (obj.case) return { kind: "case", data: obj.case };
    if (obj.done) return { kind: "done", data: obj.done };
    return null;
  } catch {
    return null;
  }
}
