// Serialize one trace (a single LLM call) for handing to another agent —
// copied to the clipboard or downloaded as a file. Pure functions (no DOM, no
// React) so they can be unit-tested in isolation; the clipboard/download side
// effects live in TraceRow.
import type { Trace } from "../../api/client";

/**
 * `prompt`, `params` and `tool_calls` are stored as JSON *strings*. Expand them
 * into nested structure so the dump reads as real JSON, not escaped-string-in-
 * string. Only objects/arrays are expanded — a plain-text prompt (or any scalar)
 * is left as the raw string, and an unparseable value never throws.
 */
function expand(value: string | null): unknown {
  if (value === null) return null;
  try {
    const parsed = JSON.parse(value);
    return typeof parsed === "object" && parsed !== null ? parsed : value;
  } catch {
    return value;
  }
}

/** The whole trace object as pretty-printed JSON, with prompt/params/tool_calls expanded. */
export function traceToJson(trace: Trace): string {
  return JSON.stringify(
    {
      ...trace,
      prompt: expand(trace.prompt),
      params: expand(trace.params),
      tool_calls: expand(trace.tool_calls),
    },
    null,
    2,
  );
}

/** Stable, descriptive download name, e.g. "vellum-trace-142-chat.json". */
export function traceFilename(trace: Trace): string {
  return `vellum-trace-${trace.id}-${trace.stage}.json`;
}
