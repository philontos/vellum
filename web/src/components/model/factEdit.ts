export const FACT_TEXT_MAX_CHARS = 4000;

type InvalidReason = "empty" | "too_long";

export type FactSaveDecision =
  | { kind: "invalid"; reason: InvalidReason }
  | { kind: "unchanged" }
  | { kind: "changed"; text: string };


export function validateFactDraft(
  draft: string,
  current: string,
): FactSaveDecision {
  const text = draft.trim();
  if (!text) return { kind: "invalid", reason: "empty" };
  if (Array.from(text).length > FACT_TEXT_MAX_CHARS) {
    return { kind: "invalid", reason: "too_long" };
  }
  if (text === current) return { kind: "unchanged" };
  return { kind: "changed", text };
}
