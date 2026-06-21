import type { Message } from "../api/client";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";
import { Markdown } from "./Markdown";
import { ProcessBlock } from "./ProcessBlock";
import { TypingDots } from "./TypingDots";

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
  onRetry,
  onDelete,
}: {
  m: Message;
  latest: boolean;
  streaming: boolean;
  onRetry?: () => void;
  onDelete?: (turn: number) => void;
}) {
  const { t } = useT();
  const blur = usePrivacyBlur();
  const mine = m.role === "user";
  const live = !mine && latest;
  // A stray retry / debug line can be soft-deleted out of history. Never offer it
  // on the reply still streaming in — that turn isn't persisted server-side yet.
  const deletable = !!onDelete && !(live && streaming);
  const del = () => {
    if (onDelete && window.confirm(t("chat.deleteConfirm"))) onDelete(m.turn);
  };
  const DeleteButton = deletable ? (
    <button
      type="button"
      onClick={del}
      title={t("chat.delete")}
      aria-label={t("chat.delete")}
      className="v-msg-del opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
    >
      ✕
    </button>
  ) : null;
  // The hopping dots are the "nothing has arrived yet" beat — they vanish the
  // instant any text streams in, reasoning and tool activity included.
  const nothingYet = !m.content && !m.reasoning?.trim() && !m.activity?.length;

  if (mine) {
    return (
      <div className="group flex items-start justify-end gap-1.5">
        {DeleteButton}
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
    <div className="group flex items-start justify-start gap-1.5">
      <div className="max-w-[88%]">
        <div className="v-eyebrow v-eyebrow--vellum">{t("chat.vellum")}</div>
        <ProcessBlock
          reasoning={m.reasoning}
          activity={m.activity}
          live={live}
          hasContent={!!m.content}
        />
        <div className={blur}>
          {m.content ? (
            <Markdown text={m.content} caret={live && streaming} />
          ) : live && streaming && nothingYet ? (
            <TypingDots />
          ) : live ? null : ( // thinking already shows in the gloss above; keep the answer quiet
            <Markdown text="…" />
          )}
        </div>
        {m.failed && (
          <div className="mt-2 flex items-center gap-3 text-[12px] text-muted">
            <span>{t("chat.error")}</span>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="font-medium text-accent transition-colors hover:text-accent-ink"
              >
                {t("chat.retry")}
              </button>
            )}
          </div>
        )}
      </div>
      <div className="pt-5">{DeleteButton}</div>
    </div>
  );
}
