import type {
  ConversationEvalRoundDetail,
  ConversationEvalWorkspace,
} from "../../api/conversationEvals";
import { useT } from "../../i18n";
import { Tag } from "../ui/StatusChip";
import { ModelCandidateSelect } from "./ModelCandidateSelect";

export function ConversationEvalLauncherControls({
  workspace,
  detail,
  promptChoice,
  modelCandidate,
  customName,
  customContent,
  loading,
  running,
  savingPrompt,
  onPromptChoiceChange,
  onModelCandidateChange,
  onCustomNameChange,
  onCustomContentChange,
  onSavePrompt,
  onStart,
}: {
  workspace: ConversationEvalWorkspace;
  detail: ConversationEvalRoundDetail;
  promptChoice: string;
  modelCandidate: string;
  customName: string;
  customContent: string;
  loading: boolean;
  running: boolean;
  savingPrompt: boolean;
  onPromptChoiceChange: (choice: string) => void;
  onModelCandidateChange: (candidate: string) => void;
  onCustomNameChange: (value: string) => void;
  onCustomContentChange: (value: string) => void;
  onSavePrompt: () => void;
  onStart: () => void;
}) {
  const { t } = useT();
  const selectedModel = workspace.model_candidates.find(
    (candidate) => candidate.id === modelCandidate,
  );
  const canRun = Boolean(
    promptChoice
    && selectedModel?.configured
    && !loading
    && !running
    && (
      promptChoice !== "new"
      || (customName.trim() && customContent.trim())
    ),
  );
  return (
    <section className="flex-none border-b border-line bg-surface/35 px-4 py-3">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
            <span>{t("eval.selectedInput")}</span>
            <Tag>{detail.round.stream}</Tag>
            <span className="font-mono normal-case tracking-normal">turn {detail.round.user_turn}</span>
          </div>
          <div
            role="region"
            aria-label={t("eval.selectedInput")}
            data-scroll-region="eval-selected-input"
            tabIndex={0}
            className="mt-2 max-h-36 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-line/60 bg-well/45 px-3 py-2 text-sm leading-relaxed text-ink focus:outline-none focus:ring-2 focus:ring-accent/20"
          >
            {detail.round.user_content}
          </div>
        </div>
        <div className="w-[min(42rem,52%)] flex-none">
          <div className="flex items-end gap-2">
            <label className="block min-w-0 flex-1" htmlFor="eval-prompt-choice">
              <span className="block text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
                {t("eval.promptVersion")}
              </span>
              <select
                id="eval-prompt-choice"
                value={promptChoice}
                onChange={(event) => onPromptChoiceChange(event.target.value)}
                disabled={running}
                className="mt-1.5 min-h-10 w-full rounded-lg border border-line bg-well px-2.5 text-sm text-ink-soft focus:outline-none focus:ring-2 focus:ring-accent/20"
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
            </label>
            <ModelCandidateSelect
              id="eval-model-candidate"
              candidates={workspace.model_candidates}
              value={modelCandidate}
              disabled={running}
              onChange={onModelCandidateChange}
            />
            <button
              type="button"
              onClick={onStart}
              disabled={!canRun}
              className="min-h-10 flex-none rounded-lg bg-accent px-4 text-sm font-medium text-accent-fg transition-colors hover:bg-accent-ink disabled:bg-surface disabled:text-muted"
            >
              {running ? t("eval.creatingArchive") : t("eval.startEvaluation")}
            </button>
          </div>
        </div>
      </div>

      {promptChoice === "new" && (
        <div className="mt-3 border-t border-line/70 pt-3">
          <div className="overflow-hidden rounded-xl border border-line bg-well/55 shadow-card">
            <div className="flex items-start gap-4 border-b border-line bg-surface/55 px-4 py-3">
              <div className="min-w-0 flex-1">
                <label
                  className="block text-[10px] font-medium uppercase tracking-[0.14em] text-muted"
                  htmlFor="eval-system-prompt-editor"
                >
                  {t("eval.systemPrompt")}
                </label>
                <p id="eval-system-prompt-hint" className="mt-1 text-xs leading-relaxed text-ink-soft">
                  {t("eval.systemPromptHint")}
                </p>
              </div>
              <span className="flex-none pt-0.5 font-mono text-[10px] text-muted">
                {t("eval.promptCharCount", { n: customContent.length })}
              </span>
              <button
                type="button"
                onClick={() => onCustomContentChange(detail.original_system_prompt ?? "")}
                disabled={
                  savingPrompt
                  || running
                  || customContent === (detail.original_system_prompt ?? "")
                }
                className="min-h-8 flex-none rounded-lg border border-line bg-surface px-2.5 text-xs text-ink-soft transition-colors hover:bg-white/5 disabled:opacity-40"
              >
                {t("eval.resetPrompt")}
              </button>
            </div>
            <textarea
              id="eval-system-prompt-editor"
              data-editor="eval-system-prompt"
              aria-describedby="eval-system-prompt-hint"
              value={customContent}
              onChange={(event) => onCustomContentChange(event.target.value)}
              placeholder={t("eval.systemPromptPlaceholder")}
              disabled={savingPrompt || running}
              rows={14}
              className="block min-h-[18rem] max-h-[55vh] w-full resize-y border-0 bg-well/40 px-4 py-3 font-mono text-[13px] leading-6 text-ink focus:outline-none focus:ring-2 focus:ring-inset focus:ring-accent/20 disabled:opacity-60"
            />
            <div className="flex items-end gap-2 border-t border-line bg-surface/35 px-4 py-3">
              <label className="block w-full max-w-sm">
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
              <button
                type="button"
                onClick={onSavePrompt}
                disabled={savingPrompt || running || !customName.trim() || !customContent.trim()}
                className="min-h-10 flex-none rounded-lg border border-line bg-surface px-3 text-sm text-ink-soft hover:bg-white/5 disabled:opacity-50"
              >
                {savingPrompt ? t("eval.savingPrompt") : t("eval.savePrompt")}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
