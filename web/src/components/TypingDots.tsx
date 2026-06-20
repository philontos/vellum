/**
 * The "Vellum is composing" beat: three warm dots that hop in sequence like
 * notes skipping across a stave — gold, sienna, ember. Shown in the reply slot
 * until the first token lands, then swapped for the streaming manuscript.
 */
export function TypingDots() {
  return (
    <div className="v-dots" role="status" aria-label="…">
      <span />
      <span />
      <span />
    </div>
  );
}
