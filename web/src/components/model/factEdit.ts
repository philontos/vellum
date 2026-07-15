export const FACT_TEXT_MAX_CHARS = 4000;

type InvalidReason = "empty" | "too_long";

export type FactSaveDecision =
  | { kind: "invalid"; reason: InvalidReason }
  | { kind: "unchanged" }
  | { kind: "cancelled" }
  | { kind: "save"; text: string };


export function decideFactSave(
  draft: string,
  current: string,
  confirmSave: () => boolean,
): FactSaveDecision {
  const text = draft.trim();
  if (!text) return { kind: "invalid", reason: "empty" };
  if (Array.from(text).length > FACT_TEXT_MAX_CHARS) {
    return { kind: "invalid", reason: "too_long" };
  }
  if (text === current) return { kind: "unchanged" };
  if (!confirmSave()) return { kind: "cancelled" };
  return { kind: "save", text };
}
