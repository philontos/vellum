import type { Message } from "../api/client";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";
import { Markdown } from "./Markdown";
import { ProcessBlock } from "./ProcessBlock";

/**
 * One turn, set to its own side. Your words arrive on the right as a recessed,
 * gold-edged "slip" in a sans hand; Vellum answers on the left in the open serif
 * manuscript with its markdown rendered — its live reasoning/tool activity riding
 * above the reply in a collapsible block. A caret blinks in the newest reply while
 * it streams in.
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

  if (mine) {
    return (
      <div className="flex justify-end">
        <div className="v-slip max-w-[78%]">
          <div className="v-eyebrow v-eyebrow--you">{t("chat.you")}</div>
          <div className={`whitespace-pre-wrap font-sans text-[13.5px] leading-[1.62] text-ink-soft ${blur}`}>
            {m.content || "…"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[88%]">
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
    </div>
  );
}
