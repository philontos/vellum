import type { ConversationModelCandidate } from "../../api/conversationEvals";
import { useT } from "../../i18n";

function displayName(
  candidate: ConversationModelCandidate,
  currentModel: string,
  notConfigured: string,
): string {
  const name = candidate.id === "primary" ? currentModel : candidate.name;
  return [
    name,
    candidate.model || null,
    candidate.configured ? null : notConfigured,
  ].filter(Boolean).join(" · ");
}

export function ModelCandidateSelect({
  id,
  candidates,
  value,
  disabled,
  onChange,
  compact = false,
}: {
  id: string;
  candidates: ConversationModelCandidate[];
  value: string;
  disabled: boolean;
  onChange: (candidate: string) => void;
  compact?: boolean;
}) {
  const { t } = useT();
  return (
    <label className={compact ? "block w-64 flex-none" : "block min-w-0 flex-1"}>
      <span className={
        compact
          ? "sr-only"
          : "block text-[10px] font-medium uppercase tracking-[0.14em] text-muted"
      }>
        {t("eval.modelCandidate")}
      </span>
      <select
        id={id}
        aria-label={t("eval.modelCandidate")}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className={
          (compact ? "min-h-9" : "mt-1.5 min-h-10")
          + " w-full rounded-lg border border-line bg-well px-2.5 text-sm text-ink-soft focus:outline-none focus:ring-2 focus:ring-accent/20 disabled:opacity-50"
        }
      >
        {candidates.map((candidate) => (
          <option
            key={candidate.id}
            value={candidate.id}
            disabled={!candidate.configured}
          >
            {displayName(
              candidate,
              t("eval.currentModel"),
              t("eval.modelNotConfigured"),
            )}
          </option>
        ))}
      </select>
    </label>
  );
}
