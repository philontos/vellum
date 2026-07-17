import type { ConversationEvalRound } from "../../api/conversationEvals";
import { useT } from "../../i18n";

export function HistoryRound({
  round,
  selected,
  disabled,
  onSelect,
}: {
  round: ConversationEvalRound;
  selected: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  const { t } = useT();
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={onSelect}
      className={
        "mb-1.5 w-full rounded-lg border px-3 py-2.5 text-left transition-colors disabled:opacity-60 " +
        (selected
          ? "border-accent/50 bg-surface shadow-card"
          : "border-transparent hover:border-line hover:bg-surface/60")
      }
    >
      <div className="flex items-center gap-2 text-[10px] text-muted">
        <span>{round.stream === "neutral" ? t("eval.modeDefault") : t("eval.modeCounseling")}</span>
        <span className="font-mono">turn {round.user_turn}</span>
        {round.prompt_release_version !== null && (
          <span className="ml-auto font-mono">v{round.prompt_release_version}</span>
        )}
      </div>
      <div className="mt-1.5 line-clamp-2 text-sm leading-snug text-ink-soft">
        {round.user_content}
      </div>
      <div className="mt-1.5 truncate text-[11px] text-muted">{round.created_at}</div>
    </button>
  );
}
