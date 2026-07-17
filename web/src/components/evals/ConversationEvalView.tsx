import type {
  ConversationEvalRoundDetail,
  ConversationEvalWorkspace,
} from "../../api/conversationEvals";
import { useT } from "../../i18n";
import { Tag } from "../ui/StatusChip";
import { HistoryRound } from "./HistoryRound";
import { ResultCard, selectedPromptLabel } from "./ResultCard";

export function ConversationEvalView({
  workspace,
  detail,
  selectedTurn,
  promptChoice,
  customName,
  customContent,
  loading,
  running,
  savingPrompt,
  error,
  liveOutput,
  onSelectRound,
  onPromptChoiceChange,
  onCustomNameChange,
  onCustomContentChange,
  onSavePrompt,
  onRun,
  onLoadMore,
  onRefresh,
  loadingMore = false,
}: {
  workspace: ConversationEvalWorkspace;
  detail: ConversationEvalRoundDetail | null;
  selectedTurn: number | null;
  promptChoice: string;
  customName: string;
  customContent: string;
  loading: boolean;
  running: boolean;
  savingPrompt: boolean;
  error: string;
  liveOutput: string;
  onSelectRound: (turn: number) => void;
  onPromptChoiceChange: (choice: string) => void;
  onCustomNameChange: (value: string) => void;
  onCustomContentChange: (value: string) => void;
  onSavePrompt: () => void;
  onRun: () => void;
  onLoadMore: () => void;
  onRefresh: () => void;
  loadingMore?: boolean;
}) {
  const { t } = useT();

  return (
    <div className="v-canvas flex h-full min-h-0 flex-col">
      <header className="flex flex-none items-center gap-4 border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h2 className="font-serif text-xl text-ink">{t("eval.replayTitle")}</h2>
          <p className="mt-0.5 truncate text-xs text-muted">{t("eval.replaySubtitle")}</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading || running}
          className="ml-auto min-h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink-soft transition-colors hover:bg-white/5 disabled:opacity-50"
        >
          {t("eval.refresh")}
        </button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[19rem_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col border-r border-line bg-well/35">
          <div className="flex-none border-b border-line px-3 py-3">
            <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
              {t("eval.historyTitle")}
            </div>
            <div className="mt-1 text-xs text-ink-soft">
              {t("eval.historyCount", { n: workspace.rounds.length })}
            </div>
          </div>
          <div
            data-scroll-region="eval-history"
            className="min-h-0 flex-1 overflow-y-auto p-2"
          >
            {workspace.rounds.map((round) => (
              <HistoryRound
                key={round.assistant_turn}
                round={round}
                selected={selectedTurn === round.assistant_turn}
                disabled={running}
                onSelect={() => onSelectRound(round.assistant_turn)}
              />
            ))}
            {workspace.rounds.length === 0 && !loading && (
              <div className="px-2 py-6 text-sm text-muted">{t("eval.noHistory")}</div>
            )}
            {workspace.has_more && (
              <button
                type="button"
                onClick={onLoadMore}
                disabled={loadingMore}
                className="mt-2 min-h-10 w-full rounded-lg border border-line text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50"
              >
                {loadingMore ? t("eval.loading") : t("eval.loadEarlier")}
              </button>
            )}
          </div>
        </aside>

        <main className="flex min-h-0 min-w-0 flex-col overflow-hidden">
          {error && (
            <div role="alert" className="flex-none border-b border-status-warn-fg/30 bg-status-warn-bg px-4 py-2 text-sm text-status-warn-fg">
              {error}
            </div>
          )}
          {detail ? (
            <>
              <ReplayControls
                workspace={workspace}
                detail={detail}
                promptChoice={promptChoice}
                customName={customName}
                customContent={customContent}
                loading={loading}
                running={running}
                savingPrompt={savingPrompt}
                onPromptChoiceChange={onPromptChoiceChange}
                onCustomNameChange={onCustomNameChange}
                onCustomContentChange={onCustomContentChange}
                onSavePrompt={onSavePrompt}
                onRun={onRun}
              />

              <section className="flex min-h-0 flex-1 flex-col">
                <div className="flex flex-none items-center gap-2 px-4 py-3">
                  <h3 className="font-serif text-lg text-ink">{t("eval.comparisonTitle")}</h3>
                  <span className="text-xs text-muted">
                    {t("eval.resultCount", { n: detail.runs.length })}
                  </span>
                  <span className="ml-auto text-xs text-muted">{t("eval.scrollHint")}</span>
                </div>
                <div
                  data-scroll-region="eval-comparison"
                  className="min-h-0 flex-1 overflow-x-auto overflow-y-hidden px-4 pb-4"
                >
                  <div className="flex h-full min-w-max items-stretch gap-3">
                    <ResultCard
                      title={t("eval.originalAnswer")}
                      label={detail.round.prompt_release_version !== null
                        ? t("eval.releaseVersion", { version: detail.round.prompt_release_version })
                        : t("eval.originalPrompt")}
                      output={detail.round.original_content}
                      status="original"
                      model={detail.round.model}
                    />
                    {running && (
                      <ResultCard
                        title={t("eval.generating")}
                        label={selectedPromptLabel(
                          workspace, detail.round, promptChoice, t("eval.newPrompt"),
                        )}
                        output={liveOutput}
                        status="running"
                        model={null}
                        live
                      />
                    )}
                    {detail.runs.map((run, index) => (
                      <ResultCard
                        key={run.id}
                        title={t("eval.generatedResult", { n: detail.runs.length - index })}
                        label={run.prompt_label}
                        output={run.output ?? ""}
                        status={run.status}
                        model={run.model}
                        run={run}
                      />
                    ))}
                  </div>
                </div>
              </section>
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center px-8 text-center text-sm text-muted">
              {loading ? t("eval.loading") : t("eval.chooseRound")}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function ReplayControls({
  workspace,
  detail,
  promptChoice,
  customName,
  customContent,
  loading,
  running,
  savingPrompt,
  onPromptChoiceChange,
  onCustomNameChange,
  onCustomContentChange,
  onSavePrompt,
  onRun,
}: {
  workspace: ConversationEvalWorkspace;
  detail: ConversationEvalRoundDetail;
  promptChoice: string;
  customName: string;
  customContent: string;
  loading: boolean;
  running: boolean;
  savingPrompt: boolean;
  onPromptChoiceChange: (choice: string) => void;
  onCustomNameChange: (value: string) => void;
  onCustomContentChange: (value: string) => void;
  onSavePrompt: () => void;
  onRun: () => void;
}) {
  const { t } = useT();
  const canRun = Boolean(promptChoice && !loading && !running);
  return (
    <section className="flex-none border-b border-line bg-surface/35 px-4 py-3">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
            <span>{t("eval.selectedInput")}</span>
            <Tag>{detail.round.stream}</Tag>
            <span className="font-mono normal-case tracking-normal">turn {detail.round.user_turn}</span>
          </div>
          <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-ink">
            {detail.round.user_content}
          </p>
        </div>
        <div className="w-[min(28rem,42%)] flex-none">
          <label className="block text-[10px] font-medium uppercase tracking-[0.14em] text-muted" htmlFor="eval-prompt-choice">
            {t("eval.promptVersion")}
          </label>
          <div className="mt-1.5 flex gap-2">
            <select
              id="eval-prompt-choice"
              value={promptChoice}
              onChange={(event) => onPromptChoiceChange(event.target.value)}
              disabled={running}
              className="min-h-10 min-w-0 flex-1 rounded-lg border border-line bg-well px-2.5 text-sm text-ink-soft focus:outline-none focus:ring-2 focus:ring-accent/20"
            >
              <option value="original" disabled={!detail.round.replayable}>
                {detail.round.prompt_release_version !== null
                  ? t("eval.originalPromptVersion", { version: detail.round.prompt_release_version })
                  : t("eval.originalPrompt")}
              </option>
              {workspace.releases.map((release) => (
                <option key={release.id} value={`release:${release.id}`}>
                  {t("eval.releaseVersion", { version: release.version })}
                  {release.is_active ? ` · ${t("eval.active")}` : ""}
                  {release.note ? ` · ${release.note}` : ""}
                </option>
              ))}
              {workspace.prompt_versions.map((version) => (
                <option key={version.id} value={`custom:${version.id}`}>
                  {version.name}
                </option>
              ))}
              <option value="new">{t("eval.newPrompt")}</option>
            </select>
            <button
              type="button"
              onClick={onRun}
              disabled={!canRun}
              className="min-h-10 flex-none rounded-lg bg-accent px-4 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-ink disabled:bg-surface disabled:text-muted"
            >
              {running
                ? t("eval.generating")
                : detail.runs.length > 0
                  ? t("eval.runAgain")
                  : t("eval.run")}
            </button>
          </div>
        </div>
      </div>

      {promptChoice === "new" && (
        <div className="mt-3 grid grid-cols-[14rem_minmax(0,1fr)_auto] items-end gap-2 border-t border-line/70 pt-3">
          <label className="block">
            <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
              {t("eval.promptName")}
            </span>
            <input
              value={customName}
              onChange={(event) => onCustomNameChange(event.target.value)}
              placeholder={t("eval.promptNamePlaceholder")}
              disabled={savingPrompt || running}
              className="mt-1 min-h-10 w-full rounded-lg border border-line bg-well px-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent/20"
            />
          </label>
          <label className="block">
            <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
              {t("eval.systemPrompt")}
            </span>
            <textarea
              value={customContent}
              onChange={(event) => onCustomContentChange(event.target.value)}
              placeholder={t("eval.systemPromptPlaceholder")}
              disabled={savingPrompt || running}
              rows={3}
              className="mt-1 max-h-40 min-h-[5rem] w-full resize-y rounded-lg border border-line bg-well px-3 py-2 font-mono text-xs leading-relaxed text-ink focus:outline-none focus:ring-2 focus:ring-accent/20"
            />
          </label>
          <button
            type="button"
            onClick={onSavePrompt}
            disabled={savingPrompt || running || !customName.trim() || !customContent.trim()}
            className="min-h-10 rounded-lg border border-line bg-surface px-3 text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50"
          >
            {savingPrompt ? t("eval.savingPrompt") : t("eval.savePrompt")}
          </button>
        </div>
      )}
    </section>
  );
}
