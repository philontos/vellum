import type { Message } from "../api/client";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";
import { Markdown } from "./Markdown";
import { ProcessBlock } from "./ProcessBlock";

/**
 * One entry in the ledger. The two voices are set off, not bubbled: your words
 * arrive as a recessed, gold-edged "slip" in a sans hand; Vellum answers in the
 * open serif manuscript with its markdown rendered. The newest reply's mark
 * glows and a caret blinks there while it streams in.
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
      {mine ? (
        <div className="v-slip">
          <div className="v-eyebrow v-eyebrow--you">{t("chat.you")}</div>
          <div className={`whitespace-pre-wrap font-sans text-[13.5px] leading-[1.62] text-ink-soft ${blur}`}>
            {m.content || "…"}
          </div>
        </div>
      ) : (
        <div>
          <div className="v-eyebrow v-eyebrow--vellum">{t("chat.vellum")}</div>
          <ProcessBlock
            reasoning={m.reasoning}
            activity={m.activity}
            live={live}
            hasContent={!!m.content}
          />
          <div className={blur}>
            <Markdown text={m.content || "…"} caret={live && streaming} />
          </div>
        </div>
      )}
    </div>
  );
}
