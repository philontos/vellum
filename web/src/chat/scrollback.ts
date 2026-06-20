import type { Message } from "../api/client";

/**
 * Merge an older batch (oldest->newest) ahead of the currently loaded window,
 * for the chat view's bounded scroll-up. Drops turns already present, and caps
 * the total at `cap` by keeping the newest of the older batch (the ones nearest
 * what's already shown). `atCap` signals there's no point loading further — the
 * rest lives in the diary.
 */
export function prependEarlier(
  existing: Message[],
  older: Message[],
  cap: number,
): { messages: Message[]; atCap: boolean } {
  const seen = new Set(existing.map((m) => m.turn));
  const fresh = older.filter((m) => !seen.has(m.turn));
  const room = Math.max(0, cap - existing.length);
  const take = fresh.slice(Math.max(0, fresh.length - room));
  const messages = [...take, ...existing];
  return { messages, atCap: messages.length >= cap };
}
