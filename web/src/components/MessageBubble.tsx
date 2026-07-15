import { useRef } from "react";

import type { Message } from "../api/client";
import { useConfirm } from "../confirm/ConfirmProvider";
import { useT } from "../i18n";
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
  const confirm = useConfirm();
  const confirmingDelete = useRef(false);
  const mine = m.role === "user";
  const live = !mine && latest;
  // A stray retry / debug line can be soft-deleted out of history. Never offer it
  // on the reply still streaming in — that turn isn't persisted server-side yet.
  const deletable = !!onDelete && !(live && streaming);
  const del = async () => {
    if (!onDelete || confirmingDelete.current) return;
    confirmingDelete.current = true;
    try {
      const approved = await confirm({
        title: t("chat.deleteTitle"),
        message: t("chat.deleteConfirm"),
        confirmLabel: t("dialog.delete"),
        cancelLabel: t("dialog.cancel"),
        tone: "danger",
      });
      if (approved) onDelete(m.turn);
    } finally {
      confirmingDelete.current = false;
    }
  };
  const DeleteButton = deletable ? (
    <button
      type="button"
      onClick={() => void del()}
      title={t("chat.delete")}
      aria-label={t("chat.delete")}
      className="v-msg-del opacity-70 sm:opacity-0 transition-opacity sm:group-hover:opacity-100 sm:focus-visible:opacity-100"
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
        <div className="v-slip max-w-[88%] break-words sm:max-w-[78%]">
          <div className="v-eyebrow v-eyebrow--you">{t("chat.you")}</div>
          <div className="whitespace-pre-wrap font-sans text-[13.5px] leading-[1.62] text-ink-soft">
            {m.content || "…"}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="group flex items-start justify-start gap-1.5">
      <div className="min-w-0 max-w-[calc(100%_-_2.5rem)] sm:max-w-[88%]">
        <div className="v-eyebrow v-eyebrow--vellum">{t("chat.vellum")}</div>
        <ProcessBlock
          reasoning={m.reasoning}
          activity={m.activity}
          live={live}
          hasContent={!!m.content}
        />
        <div>
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
