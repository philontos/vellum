import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type {
  ConversationEvalRoundDetail,
  ConversationEvalWorkspace,
} from "../api/conversationEvals";
import { I18nProvider } from "../i18n";
import { ConversationEvalView } from "./EvalPanel";

const WORKSPACE: ConversationEvalWorkspace = {
  rounds: [
    {
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
    },
    {
      user_turn: 18,
      assistant_turn: 19,
      stream: "freud",
      user_content: "Why am I avoiding it?",
      original_content: "You may be protecting an identity.",
      created_at: "2026-07-16 08:00:00",
      trace_id: 2,
      prompt_release_id: 6,
      prompt_release_version: 3,
      model: "model-a",
      replayable: true,
    },
  ],
  releases: [
    { id: 7, version: 4, note: "current", published_at: "2026-07-17", is_active: true },
    { id: 6, version: 3, note: "before tuning", published_at: "2026-07-16", is_active: false },
  ],
  prompt_versions: [
    { id: 2, name: "More direct", content: "Be direct.", created_at: "2026-07-17" },
  ],
  has_more: true,
};

const DETAIL: ConversationEvalRoundDetail = {
  round: WORKSPACE.rounds[0],
  original_system_prompt: "Original system prompt",
  runs: [
    {
      id: 11,
      source_user_turn: 20,
      source_assistant_turn: 21,
      stream: "neutral",
      prompt_kind: "release",
      prompt_release_id: 7,
      prompt_release_version: 4,
      prompt_version_id: null,
      prompt_label: "Release v4",
      model: "model-a",
      status: "done",
      output: "Generated answer A",
      error: null,
      prompt_tokens: 120,
      completion_tokens: 40,
      duration_ms: 900,
      created_at: "2026-07-17 09:00:00",
      finished_at: "2026-07-17 09:00:01",
    },
    {
      id: 10,
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
      created_at: "2026-07-17 08:30:00",
      finished_at: "2026-07-17 08:30:01",
    },
  ],
};

describe("ConversationEvalView", () => {
  it("renders history selection, Prompt controls, and horizontal comparisons", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConversationEvalView
          workspace={WORKSPACE}
          detail={DETAIL}
          selectedTurn={21}
          promptChoice="release:7"
          customName=""
          customContent=""
          loading={false}
          running={false}
          savingPrompt={false}
          error=""
          liveOutput=""
          onSelectRound={() => undefined}
          onPromptChoiceChange={() => undefined}
          onCustomNameChange={() => undefined}
          onCustomContentChange={() => undefined}
          onSavePrompt={() => undefined}
          onRun={() => undefined}
          onLoadMore={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("Conversation replay");
    expect(html).toContain("How should I frame this decision?");
    expect(html).toContain("Why am I avoiding it?");
    expect(html).toContain('aria-pressed="true"');
    expect(html).toContain("Original answer");
    expect(html).toContain("Generated answer A");
    expect(html).toContain("Generated answer B");
    expect(html).toContain("Release v4");
    expect(html).toContain("More direct");
    expect(html).toContain('data-scroll-region="eval-history"');
    expect(html).toContain('data-scroll-region="eval-comparison"');
    expect(html).toContain("Run again");
    expect(html).toContain("Load earlier");
  });

  it("shows the on-the-spot Prompt editor and a live result card", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConversationEvalView
          workspace={WORKSPACE}
          detail={DETAIL}
          selectedTurn={21}
          promptChoice="new"
          customName="Trial prompt"
          customContent="Match the user&#39;s language."
          loading={false}
          running
          savingPrompt={false}
          error=""
          liveOutput="Still generating"
          onSelectRound={() => undefined}
          onPromptChoiceChange={() => undefined}
          onCustomNameChange={() => undefined}
          onCustomContentChange={() => undefined}
          onSavePrompt={() => undefined}
          onRun={() => undefined}
          onLoadMore={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("Save Prompt version");
    expect(html).toContain("Trial prompt");
    expect(html).toContain("Still generating");
    expect(html).toContain("Generating…");
  });
});
