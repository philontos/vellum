import type { Message } from "../api/client";

/**
 * Drop the message at `turn` from the loaded chat window, preserving order. The
 * local mirror of a soft-delete (see api.deleteMessage) — the server has already
 * hidden it from history, this just takes it out of the view in place.
 */
export function removeTurn(messages: Message[], turn: number): Message[] {
  return messages.filter((m) => m.turn !== turn);
}
