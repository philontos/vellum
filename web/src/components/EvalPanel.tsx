import { useEffect, useState } from "react";

import {
  createConversationPromptVersion,
  getConversationEvalRound,
  getConversationEvalWorkspace,
  streamConversationEvalRun,
  type ConversationEvalRound,
  type ConversationEvalRoundDetail,
  type ConversationEvalRunRequest,
  type ConversationEvalWorkspace,
  type ConversationPromptVersion,
} from "../api/conversationEvals";
import { ConversationEvalView } from "./evals/ConversationEvalView";

export { ConversationEvalView } from "./evals/ConversationEvalView";

const PAGE_SIZE = 50;

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function defaultChoice(
  round: ConversationEvalRound,
  workspace: ConversationEvalWorkspace,
): string {
  if (round.replayable) return "original";
  if (
    round.prompt_release_id !== null
    && workspace.releases.some((release) => release.id === round.prompt_release_id)
  ) return `release:${round.prompt_release_id}`;
  const active = workspace.releases.find((release) => release.is_active);
  if (active) return `release:${active.id}`;
  if (workspace.prompt_versions[0]) return `custom:${workspace.prompt_versions[0].id}`;
  return "new";
}

export function EvalPanel() {
  const [workspace, setWorkspace] = useState<ConversationEvalWorkspace | null>(null);
  const [detail, setDetail] = useState<ConversationEvalRoundDetail | null>(null);
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);
  const [promptChoice, setPromptChoice] = useState("");
  const [customName, setCustomName] = useState("");
  const [customContent, setCustomContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [running, setRunning] = useState(false);
  const [liveOutput, setLiveOutput] = useState("");
  const [error, setError] = useState("");

  async function loadRound(
    turn: number,
    source: ConversationEvalWorkspace,
  ): Promise<void> {
    setLoading(true);
    setError("");
    try {
      const next = await getConversationEvalRound(turn);
      setSelectedTurn(turn);
      setDetail(next);
      setPromptChoice(defaultChoice(next.round, source));
      setCustomName("");
      setCustomContent(next.original_system_prompt ?? "");
    } catch (loadError) {
      setError(message(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function loadInitial(preferredTurn?: number | null): Promise<void> {
    setLoading(true);
    setError("");
    try {
      const next = await getConversationEvalWorkspace({ limit: PAGE_SIZE });
      setWorkspace(next);
      const selected = next.rounds.find(
        (round) => round.assistant_turn === preferredTurn,
      ) ?? next.rounds[0];
      if (selected) {
        const nextDetail = await getConversationEvalRound(selected.assistant_turn);
        setSelectedTurn(selected.assistant_turn);
        setDetail(nextDetail);
        setPromptChoice(defaultChoice(nextDetail.round, next));
        setCustomContent(nextDetail.original_system_prompt ?? "");
      } else {
        setSelectedTurn(null);
        setDetail(null);
        setPromptChoice("");
      }
    } catch (loadError) {
      setError(message(loadError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadInitial();
  }, []);

  async function loadMore() {
    if (!workspace?.has_more || loadingMore || workspace.rounds.length === 0) return;
    setLoadingMore(true);
    setError("");
    try {
      const before = workspace.rounds[workspace.rounds.length - 1].assistant_turn;
      const page = await getConversationEvalWorkspace({ limit: PAGE_SIZE, before });
      setWorkspace({
        ...workspace,
        rounds: [...workspace.rounds, ...page.rounds],
        releases: page.releases,
        prompt_versions: page.prompt_versions,
        has_more: page.has_more,
      });
    } catch (loadError) {
      setError(message(loadError));
    } finally {
      setLoadingMore(false);
    }
  }

  async function savePrompt(): Promise<ConversationPromptVersion | null> {
    if (!workspace || savingPrompt) return null;
    setSavingPrompt(true);
    setError("");
    try {
      const version = await createConversationPromptVersion(customName, customContent);
      setWorkspace({
        ...workspace,
        prompt_versions: [version, ...workspace.prompt_versions],
      });
      setPromptChoice(`custom:${version.id}`);
      return version;
    } catch (saveError) {
      setError(message(saveError));
      return null;
    } finally {
      setSavingPrompt(false);
    }
  }

  function requestFor(choice: string): ConversationEvalRunRequest | null {
    if (selectedTurn === null) return null;
    if (choice === "original") {
      return { assistant_turn: selectedTurn, prompt_kind: "original" };
    }
    const [kind, rawId] = choice.split(":");
    const id = Number(rawId);
    if (!Number.isInteger(id)) return null;
    if (kind === "release") {
      return {
        assistant_turn: selectedTurn,
        prompt_kind: "release",
        prompt_release_id: id,
      };
    }
    if (kind === "custom") {
      return {
        assistant_turn: selectedTurn,
        prompt_kind: "custom",
        prompt_version_id: id,
      };
    }
    return null;
  }

  async function run() {
    if (!detail || running) return;
    let choice = promptChoice;
    if (choice === "new") {
      const version = await savePrompt();
      if (!version) return;
      choice = `custom:${version.id}`;
    }
    const request = requestFor(choice);
    if (!request) return;

    setRunning(true);
    setLiveOutput("");
    setError("");
    try {
      await streamConversationEvalRun(request, {
        onDelta: (text) => setLiveOutput((current) => current + text),
        onDone: (result) => {
          setDetail((current) => current && {
            ...current,
            runs: [result, ...current.runs.filter((run) => run.id !== result.id)],
          });
        },
      });
    } catch (runError) {
      setError(message(runError));
    } finally {
      setRunning(false);
      setLiveOutput("");
    }
  }

  const emptyWorkspace: ConversationEvalWorkspace = {
    rounds: [], releases: [], prompt_versions: [], has_more: false,
  };

  return (
    <ConversationEvalView
      workspace={workspace ?? emptyWorkspace}
      detail={detail}
      selectedTurn={selectedTurn}
      promptChoice={promptChoice}
      customName={customName}
      customContent={customContent}
      loading={loading}
      running={running}
      savingPrompt={savingPrompt}
      error={error}
      liveOutput={liveOutput}
      onSelectRound={(turn) => {
        if (workspace && turn !== selectedTurn && !running) void loadRound(turn, workspace);
      }}
      onPromptChoiceChange={(choice) => {
        setPromptChoice(choice);
        if (choice === "new" && !customContent) {
          setCustomContent(detail?.original_system_prompt ?? "");
        }
      }}
      onCustomNameChange={setCustomName}
      onCustomContentChange={setCustomContent}
      onSavePrompt={() => void savePrompt()}
      onRun={() => void run()}
      onLoadMore={() => void loadMore()}
      onRefresh={() => void loadInitial(selectedTurn)}
      loadingMore={loadingMore}
    />
  );
}
