import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type {
  ConversationEvalRecordDetail,
  ConversationEvalRecordSummary,
  ConversationEvalRoundDetail,
  ConversationEvalWorkspace,
} from "../api/conversationEvals";
import { I18nProvider } from "../i18n";
import { ConversationEvalView, defaultModelCandidate } from "./EvalPanel";
import { ConversationEvalArchiveList } from "./evals/ConversationEvalArchiveList";
import { ConversationEvalRecordView } from "./evals/ConversationEvalRecordView";

const WORKSPACE: ConversationEvalWorkspace = {
  default_model_candidate: "glm",
  model_candidates: [
    { id: "primary", name: "Primary model", model: "model-a", configured: true },
    { id: "glm", name: "GLM", model: "glm-5.2", configured: true },
    { id: "kimi", name: "Kimi K3", model: "kimi-k3", configured: false },
  ],
  rounds: [{
    user_turn: 20,
    assistant_turn: 21,
    stream: "neutral",
    user_content: "How should I frame this decision?",
    original_content: "Start with the irreversible part.",
    created_at: "2026-07-17 08:00:00",
    trace_id: 3,
    prompt_release_id: 7,
    prompt_release_version: 4,
    model: "model-a",
    replayable: true,
  }],
  releases: [
    { id: 7, version: 4, note: "current", published_at: "2026-07-17", is_active: true },
  ],
  prompt_versions: [
    { id: 2, name: "More direct", content: "Be direct.", created_at: "2026-07-17" },
  ],
  has_more: true,
};

const SOURCE: ConversationEvalRoundDetail = {
  round: WORKSPACE.rounds[0],
  original_system_prompt: "You are helpful.\nBe concise.",
};

const RECORD: ConversationEvalRecordDetail = {
  id: 23,
  source_user_turn: 20,
  source_assistant_turn: 21,
  stream: "neutral",
  source_created_at: "2026-07-17 08:00:00",
  source_user_content: "How should I frame this decision?",
  baseline_output: "Start with the irreversible part.",
  baseline_prompt_release_id: 7,
  baseline_prompt_release_version: 4,
  baseline_prompt_label: "Original · v4",
  baseline_system_prompt: "You are helpful.\nBe concise.",
  baseline_input: [
    { role: "system", content: "You are helpful.\nBe concise." },
    { role: "user", content: "How should I frame this decision?" },
  ],
  prompt_kind: "custom",
  prompt_release_id: null,
  prompt_release_version: null,
  prompt_version_id: 2,
  prompt_label: "More direct",
  system_prompt: "You are direct.\nBe concise.",
  input: [
    { role: "system", content: "You are direct.\nBe concise." },
    { role: "user", content: "How should I frame this decision?" },
  ],
  run_count: 2,
  latest_status: "done",
  latest_output: "Generated answer B",
  created_at: "2026-07-17 09:00:00",
  runs: [
    {
      id: 11,
      record_id: 23,
      source_user_turn: 20,
      source_assistant_turn: 21,
      stream: "neutral",
      prompt_kind: "custom",
      prompt_release_id: null,
      prompt_release_version: null,
      prompt_version_id: 2,
      prompt_label: "More direct",
      model: "model-a",
      status: "done",
      output: "Generated answer B",
      error: null,
      prompt_tokens: 100,
      completion_tokens: 32,
      duration_ms: 700,
      created_at: "2026-07-17 09:00:00",
      finished_at: "2026-07-17 09:00:01",
    },
  ],
};

const SUMMARY: ConversationEvalRecordSummary = {
  id: RECORD.id,
  source_user_turn: RECORD.source_user_turn,
  source_assistant_turn: RECORD.source_assistant_turn,
  stream: RECORD.stream,
  source_user_content: RECORD.source_user_content,
  baseline_output: RECORD.baseline_output,
  baseline_prompt_label: RECORD.baseline_prompt_label,
  prompt_kind: RECORD.prompt_kind,
  prompt_release_id: RECORD.prompt_release_id,
  prompt_release_version: RECORD.prompt_release_version,
  prompt_version_id: RECORD.prompt_version_id,
  prompt_label: RECORD.prompt_label,
  run_count: RECORD.run_count,
  latest_status: RECORD.latest_status,
  latest_output: RECORD.latest_output,
  created_at: RECORD.created_at,
};

describe("conversation evaluation views", () => {
  it("uses the evaluation scenario route as the initial candidate", () => {
    expect(defaultModelCandidate(WORKSPACE)).toBe("glm");
  });

  it("keeps the historical source picker focused on starting an archive", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConversationEvalView
          workspace={WORKSPACE}
          detail={SOURCE}
          selectedTurn={21}
          promptChoice="new"
          modelCandidate="glm"
          customName="Trial prompt"
          customContent="You are direct."
          archiveCount={3}
          loading={false}
          running={false}
          savingPrompt={false}
          error=""
          onSelectRound={() => undefined}
          onPromptChoiceChange={() => undefined}
          onModelCandidateChange={() => undefined}
          onCustomNameChange={() => undefined}
          onCustomContentChange={() => undefined}
          onSavePrompt={() => undefined}
          onStartEvaluation={() => undefined}
          onOpenArchive={() => undefined}
          onLoadMore={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("Start evaluation");
    expect(html).toContain("Candidate model");
    expect(html).toContain("GLM · glm-5.2");
    expect(html).toContain("Kimi K3 · kimi-k3 · not configured");
    expect(html).toContain('id="eval-model-candidate"');
    expect(html).toContain("Evaluation archive · 3");
    expect(html).toContain('data-scroll-region="eval-history"');
    expect(html).toContain('data-scroll-region="eval-selected-input"');
    expect(html).toContain('data-editor="eval-system-prompt"');
    expect(html).toContain("Baseline result preview");
    expect(html).not.toContain("Generated answer B");
  });

  it("renders the archive index independently of historical source selection", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConversationEvalArchiveList
          records={[SUMMARY]}
          hasMore
          loading={false}
          loadingMore={false}
          error=""
          onOpen={() => undefined}
          onNew={() => undefined}
          onRefresh={() => undefined}
          onLoadMore={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("Evaluation archive");
    expect(html).toContain("Evaluation #23");
    expect(html).toContain("More direct");
    expect(html).toContain("2 runs");
    expect(html).toContain("Generated answer B");
    expect(html).toContain('data-eval-record="23"');
  });

  it("shows Prompt metadata, full snapshots, diff, and all results in record detail", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConversationEvalRecordView
          record={RECORD}
          modelCandidates={WORKSPACE.model_candidates}
          modelCandidate="glm"
          running={false}
          liveOutput=""
          error=""
          onBack={() => undefined}
          onRunAgain={() => undefined}
          onModelCandidateChange={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain('data-eval-record-detail="23"');
    expect(html).toContain("Evaluation #23");
    expect(html).toContain("More direct");
    expect(html).toContain("Original · v4");
    expect(html).toContain("Prompt diff");
    expect(html).toContain("Evaluated Prompt");
    expect(html).toContain("Baseline Prompt");
    expect(html).toContain("Full model inputs");
    expect(html).toContain("You are helpful.");
    expect(html).toContain("You are direct.");
    expect(html).toContain("Start with the irreversible part.");
    expect(html).toContain("Generated answer B");
    expect(html).toContain('id="eval-record-model-candidate"');
  });
});
