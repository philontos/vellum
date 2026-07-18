import type {
  ConversationEvalRecordDetail,
  ConversationModelCandidate,
} from "../../api/conversationEvals";
import { useT } from "../../i18n";
import { Tag } from "../ui/StatusChip";
import { PromptInspector } from "./PromptInspector";
import { ResultCard } from "./ResultCard";
import { ModelCandidateSelect } from "./ModelCandidateSelect";

export function ConversationEvalRecordView({
  record,
  modelCandidates,
  modelCandidate,
  running,
  liveOutput,
  error,
  onBack,
  onRunAgain,
  onModelCandidateChange,
  onRefresh,
}: {
  record: ConversationEvalRecordDetail;
  modelCandidates: ConversationModelCandidate[];
  modelCandidate: string;
  running: boolean;
  liveOutput: string;
  error: string;
  onBack: () => void;
  onRunAgain: () => void;
  onModelCandidateChange: (candidate: string) => void;
  onRefresh: () => void;
}) {
  const { t } = useT();
  const kindLabel = record.prompt_kind === "release"
    ? t("eval.promptKindRelease")
    : record.prompt_kind === "custom"
      ? t("eval.promptKindCustom")
      : t("eval.promptKindOriginal");
  const selectedModel = modelCandidates.find(
    (candidate) => candidate.id === modelCandidate,
  );
  return (
    <div
      data-eval-record-detail={record.id}
      className="v-canvas flex h-full min-h-0 flex-col"
    >
      <header className="flex flex-none items-center gap-3 border-b border-line px-4 py-3">
        <button
          type="button"
          onClick={onBack}
          className="min-h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink-soft hover:bg-white/5"
        >
          ← {t("eval.backToArchive")}
        </button>
        <div className="min-w-0">
          <h2 className="font-serif text-xl text-ink">
            {t("eval.recordTitle", { id: record.id })}
          </h2>
          <p className="mt-0.5 truncate font-mono text-[10px] text-muted">
            {record.created_at}
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={running}
          className="ml-auto min-h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50"
        >
          {t("eval.refresh")}
        </button>
        <ModelCandidateSelect
          id="eval-record-model-candidate"
          candidates={modelCandidates}
          value={modelCandidate}
          disabled={running}
          onChange={onModelCandidateChange}
          compact
        />
        <button
          type="button"
          onClick={onRunAgain}
          disabled={running || !selectedModel?.configured}
          className="min-h-9 rounded-lg bg-accent px-4 text-sm font-medium text-accent-fg hover:bg-accent-ink disabled:bg-surface disabled:text-muted"
        >
          {running ? t("eval.generating") : t("eval.runAgain")}
        </button>
      </header>

      {error && (
        <div role="alert" className="flex-none border-b border-status-warn-fg/30 bg-status-warn-bg px-4 py-2 text-sm text-status-warn-fg">
          {error}
        </div>
      )}

      <main data-scroll-region="eval-record-detail" className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <div className="mx-auto max-w-[96rem] space-y-4">
          <section className="grid grid-cols-[minmax(0,1fr)_minmax(22rem,0.72fr)] gap-3">
            <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
              <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
                <span>{t("eval.recordSource")}</span>
                <Tag>{record.stream}</Tag>
                <span className="font-mono normal-case tracking-normal">
                  turn {record.source_user_turn}
                </span>
              </div>
              <div className="mt-3 max-h-36 overflow-y-auto whitespace-pre-wrap break-words text-sm leading-relaxed text-ink">
                {record.source_user_content}
              </div>
            </div>
            <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
              <div className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
                {t("eval.promptVersion")}
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Tag>{kindLabel}</Tag>
                <span className="font-mono text-sm text-ink">{record.prompt_label}</span>
                {record.prompt_release_version !== null && (
                  <span className="font-mono text-[10px] text-muted">
                    {t("eval.releaseRef", { version: record.prompt_release_version })}
                  </span>
                )}
                {record.prompt_version_id !== null && (
                  <span className="font-mono text-[10px] text-muted">
                    {t("eval.savedPromptRef", { id: record.prompt_version_id })}
                  </span>
                )}
              </div>
              <div className="mt-3 text-xs text-muted">
                {t("eval.baselinePrompt")}: <span className="font-mono text-ink-soft">{record.baseline_prompt_label}</span>
              </div>
              <div className="mt-1 text-xs text-muted">
                {t("eval.count", { n: record.runs.length })}
              </div>
            </div>
          </section>

          <section>
            <h3 className="mb-2 font-serif text-lg text-ink">{t("eval.promptSnapshots")}</h3>
            <PromptInspector
              baseline={record.baseline_system_prompt}
              candidate={record.system_prompt}
              baselineInput={record.baseline_input}
              candidateInput={record.input}
            />
          </section>

          <section>
            <div className="mb-2 flex items-center gap-2">
              <h3 className="font-serif text-lg text-ink">{t("eval.comparisonTitle")}</h3>
              <span className="text-xs text-muted">
                {t("eval.count", { n: record.runs.length })}
              </span>
              <span className="ml-auto text-xs text-muted">{t("eval.scrollHint")}</span>
            </div>
            <div data-scroll-region="eval-record-results" className="h-[32rem] overflow-x-auto overflow-y-hidden pb-2">
              <div className="flex h-full min-w-max items-stretch gap-3">
                <ResultCard
                  title={t("eval.originalAnswer")}
                  label={record.baseline_prompt_label}
                  output={record.baseline_output}
                  status="original"
                  model={null}
                />
                {running && (
                  <ResultCard
                    title={t("eval.generating")}
                    label={record.prompt_label}
                    output={liveOutput}
                    status="running"
                    model={selectedModel?.model ?? null}
                    live
                  />
                )}
                {record.runs.map((run, index) => (
                  <ResultCard
                    key={run.id}
                    title={t("eval.generatedResult", { n: record.runs.length - index })}
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
        </div>
      </main>
    </div>
  );
}
