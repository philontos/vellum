import type {
  ConversationEvalRoundDetail,
  ConversationEvalWorkspace,
} from "../../api/conversationEvals";
import { useT } from "../../i18n";
import { Markdown } from "../Markdown";
import { ConversationEvalLauncherControls } from "./ConversationEvalLauncherControls";
import { HistoryRound } from "./HistoryRound";

export function ConversationEvalView({
  workspace,
  detail,
  selectedTurn,
  promptChoice,
  customName,
  customContent,
  archiveCount,
  loading,
  running,
  savingPrompt,
  error,
  onSelectRound,
  onPromptChoiceChange,
  onCustomNameChange,
  onCustomContentChange,
  onSavePrompt,
  onStartEvaluation,
  onOpenArchive,
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
  archiveCount: number;
  loading: boolean;
  running: boolean;
  savingPrompt: boolean;
  error: string;
  onSelectRound: (turn: number) => void;
  onPromptChoiceChange: (choice: string) => void;
  onCustomNameChange: (value: string) => void;
  onCustomContentChange: (value: string) => void;
  onSavePrompt: () => void;
  onStartEvaluation: () => void;
  onOpenArchive: () => void;
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
          onClick={onOpenArchive}
          className="ml-auto min-h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink-soft transition-colors hover:bg-white/5"
        >
          {t("eval.archiveWithCount", { n: archiveCount })}
        </button>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading || running}
          className="min-h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink-soft transition-colors hover:bg-white/5 disabled:opacity-50"
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
              <ConversationEvalLauncherControls
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
                onStart={onStartEvaluation}
              />

              <section data-scroll-region="eval-source-preview" className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
                <div className="mx-auto max-w-3xl rounded-xl border border-line bg-surface p-5 shadow-card">
                  <h3 className="font-serif text-lg text-ink">{t("eval.baselinePreview")}</h3>
                  <div className="mt-1 text-xs text-muted">
                    {detail.round.prompt_release_version !== null
                      ? t("eval.originalPromptVersion", { version: detail.round.prompt_release_version })
                      : t("eval.originalPrompt")}
                  </div>
                  <div className="mt-4 border-t border-line pt-4">
                    <Markdown text={detail.round.original_content} />
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
