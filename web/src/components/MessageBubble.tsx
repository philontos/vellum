import type { Message } from "../api/client";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";

/**
 * One entry in the ledger. No bubbles — speaker is read from the type
 * (Vellum = serif voice, You = sans) and a page-edge mark. The newest
 * Vellum mark glows; a caret blinks there while the reply streams in.
 */
export function MessageBubble({
  m,
  latest,
  streaming,
}: {
  m: Message;
  latest: boolean;
  streaming: boolean;
}) {
  const { t } = useT();
  const blur = usePrivacyBlur();
  const mine = m.role === "user";
  const live = !mine && latest;

  const tick = mine
    ? "border border-gold/70 bg-transparent" // your mark — a quiet gold ring
    : live
      ? "bg-accent v-glow" // newest reply — the one live spark
      : "bg-accent/40"; // earlier replies recede

  return (
    <div className="v-turn">
      <span className={`v-tick ${tick}`} aria-hidden />
      <span className="sr-only">{mine ? t("chat.you") : t("chat.vellum")}</span>
      {mine ? (
        <div className="whitespace-pre-wrap font-sans text-[13.5px] leading-[1.58] text-ink-soft">
          <span className={blur}>{m.content || "…"}</span>
        </div>
      ) : (
        <div className="whitespace-pre-wrap font-serif text-[17px] leading-[1.68] text-ink">
          <span className={blur}>{m.content || "…"}</span>
          {live && streaming && <span className="v-caret" aria-hidden />}
        </div>
      )}
    </div>
  );
}
