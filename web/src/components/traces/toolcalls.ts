// One tool call as persisted on a chat trace: the full diagnostic record of a
// single round-trip in the turn's tool loop. `raw_args` is present only when the
// model's arguments blob failed to parse (kept verbatim for debugging).
export type ToolCall = {
  name: string;
  args?: unknown;
  result?: string | null;
  ok?: boolean;
  raw_args?: string;
};

/**
 * Parse a trace's `tool_calls` JSON string into a list. Returns `[]` for null
 * (no tools ran, or the trace was pruned), malformed JSON, or a non-array
 * payload — rendering must never throw on a bad blob.
 */
export function parseToolCalls(raw: string | null | undefined): ToolCall[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as ToolCall[]) : [];
  } catch {
    return [];
  }
}
