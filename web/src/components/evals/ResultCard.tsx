import type {
  ConversationEvalRound,
  ConversationEvalRun,
  ConversationEvalWorkspace,
} from "../../api/conversationEvals";
import { useT } from "../../i18n";
import { Markdown } from "../Markdown";
import { StatusChip } from "../ui/StatusChip";

export function selectedPromptLabel(
  workspace: ConversationEvalWorkspace,
  round: ConversationEvalRound,
  choice: string,
  newPromptLabel: string,
): string {
  if (choice === "original") {
    return round.prompt_release_version !== null
      ? `Original · v${round.prompt_release_version}`
      : "Original Prompt";
  }
  const [kind, rawId] = choice.split(":");
  const id = Number(rawId);
  if (kind === "release") {
    const release = workspace.releases.find((item) => item.id === id);
    return release ? `Release v${release.version}` : choice;
  }
  if (kind === "custom") {
    return workspace.prompt_versions.find((item) => item.id === id)?.name ?? choice;
  }
  return newPromptLabel;
}

export function ResultCard({
  title,
  label,
  output,
  status,
  model,
  run,
  live = false,
}: {
  title: string;
  label: string;
  output: string;
  status: string;
  model: string | null;
  run?: ConversationEvalRun;
  live?: boolean;
}) {
  const { t } = useT();
  return (
    <article className="flex h-full w-[23rem] flex-none flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-card xl:w-[26rem]">
      <header className="flex-none border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <h4 className="font-serif text-base text-ink">{title}</h4>
          {status !== "original" && <StatusChip status={status} />}
        </div>
        <div className="mt-1.5 flex items-center gap-2 text-[11px] text-muted">
          <span className="max-w-[13rem] truncate text-ink-soft" title={label}>{label}</span>
          {model && <span className="ml-auto truncate font-mono">{model}</span>}
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {output ? (
          <Markdown text={output} caret={live} />
        ) : run?.error ? (
          <p className="text-sm leading-relaxed text-status-warn-fg">{run.error}</p>
        ) : live ? (
          <p className="text-sm text-muted">{t("eval.waitingForOutput")}<span className="v-caret" aria-hidden /></p>
        ) : (
          <p className="text-sm text-muted">{t("eval.noOutput")}</p>
        )}
      </div>
      {run && (
        <footer className="flex flex-none flex-wrap gap-x-3 gap-y-1 border-t border-line px-4 py-2 font-mono text-[10px] text-muted">
          <span>{run.prompt_tokens ?? "?"}→{run.completion_tokens ?? "?"} tok</span>
          <span>{run.duration_ms ?? "?"} ms</span>
          <span className="ml-auto">{run.created_at}</span>
        </footer>
      )}
    </article>
  );
}
