import { useEffect, useState } from "react";

import {
  createConversationEvalRecord,
  createConversationPromptVersion,
  getConversationEvalRecord,
  getConversationEvalRecords,
  getConversationEvalRound,
  getConversationEvalWorkspace,
  streamConversationEvalRecordRun,
  type ConversationEvalRecordDetail,
  type ConversationEvalRecordSummary,
  type ConversationEvalRound,
  type ConversationEvalRoundDetail,
  type ConversationEvalRunRequest,
  type ConversationEvalWorkspace,
  type ConversationPromptVersion,
} from "../api/conversationEvals";
import { ConversationEvalArchiveList } from "./evals/ConversationEvalArchiveList";
import { ConversationEvalRecordView } from "./evals/ConversationEvalRecordView";
import { ConversationEvalView } from "./evals/ConversationEvalView";

export { ConversationEvalView } from "./evals/ConversationEvalView";

const PAGE_SIZE = 50;
type EvalView = "launcher" | "archive" | "record";

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

function defaultModelCandidate(workspace: ConversationEvalWorkspace): string {
  const primary = workspace.model_candidates.find(
    (candidate) => candidate.id === "primary" && candidate.configured,
  );
  return primary?.id
    ?? workspace.model_candidates.find((candidate) => candidate.configured)?.id
    ?? "primary";
}

function summary(record: ConversationEvalRecordDetail): ConversationEvalRecordSummary {
  return {
    id: record.id,
    source_user_turn: record.source_user_turn,
    source_assistant_turn: record.source_assistant_turn,
    stream: record.stream,
    source_user_content: record.source_user_content,
    baseline_output: record.baseline_output,
    baseline_prompt_label: record.baseline_prompt_label,
    prompt_kind: record.prompt_kind,
    prompt_release_id: record.prompt_release_id,
    prompt_release_version: record.prompt_release_version,
    prompt_version_id: record.prompt_version_id,
    prompt_label: record.prompt_label,
    run_count: record.run_count,
    latest_status: record.latest_status,
    latest_output: record.latest_output,
    created_at: record.created_at,
  };
}

export function EvalPanel() {
  const [view, setView] = useState<EvalView>("launcher");
  const [workspace, setWorkspace] = useState<ConversationEvalWorkspace | null>(null);
  const [detail, setDetail] = useState<ConversationEvalRoundDetail | null>(null);
  const [records, setRecords] = useState<ConversationEvalRecordSummary[]>([]);
  const [activeRecord, setActiveRecord] = useState<ConversationEvalRecordDetail | null>(null);
  const [selectedTurn, setSelectedTurn] = useState<number | null>(null);
  const [promptChoice, setPromptChoice] = useState("");
  const [modelCandidate, setModelCandidate] = useState("primary");
  const [customName, setCustomName] = useState("");
  const [customContent, setCustomContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingArchive, setLoadingArchive] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadingMoreArchive, setLoadingMoreArchive] = useState(false);
  const [archiveHasMore, setArchiveHasMore] = useState(false);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [running, setRunning] = useState(false);
  const [liveOutput, setLiveOutput] = useState("");
  const [error, setError] = useState("");

  async function selectRound(
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
    setLoadingArchive(true);
    setError("");
    try {
      const [next, archive] = await Promise.all([
        getConversationEvalWorkspace({ limit: PAGE_SIZE }),
        getConversationEvalRecords({ limit: PAGE_SIZE }),
      ]);
      setWorkspace(next);
      setModelCandidate((current) => {
        const selected = next.model_candidates.find(
          (candidate) => candidate.id === current && candidate.configured,
        );
        return selected?.id ?? defaultModelCandidate(next);
      });
      setRecords(archive.records);
      setArchiveHasMore(archive.has_more);
      const selected = next.rounds.find(
        (round) => round.assistant_turn === preferredTurn,
      ) ?? next.rounds[0];
      if (selected) {
        const nextDetail = await getConversationEvalRound(selected.assistant_turn);
        setSelectedTurn(selected.assistant_turn);
        setDetail(nextDetail);
        setPromptChoice(defaultChoice(nextDetail.round, next));
        setCustomName("");
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
      setLoadingArchive(false);
    }
  }

  useEffect(() => {
    void loadInitial();
  }, []);

  async function refreshArchive(): Promise<void> {
    setLoadingArchive(true);
    setError("");
    try {
      const archive = await getConversationEvalRecords({ limit: PAGE_SIZE });
      setRecords(archive.records);
      setArchiveHasMore(archive.has_more);
    } catch (loadError) {
      setError(message(loadError));
    } finally {
      setLoadingArchive(false);
    }
  }

  async function loadMoreSources() {
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
        model_candidates: page.model_candidates,
        has_more: page.has_more,
      });
    } catch (loadError) {
      setError(message(loadError));
    } finally {
      setLoadingMore(false);
    }
  }

  async function loadMoreRecords() {
    if (!archiveHasMore || loadingMoreArchive || records.length === 0) return;
    setLoadingMoreArchive(true);
    setError("");
    try {
      const page = await getConversationEvalRecords({
        limit: PAGE_SIZE,
        before: records[records.length - 1].id,
      });
      setRecords((current) => [...current, ...page.records]);
      setArchiveHasMore(page.has_more);
    } catch (loadError) {
      setError(message(loadError));
    } finally {
      setLoadingMoreArchive(false);
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

  function updateRecord(record: ConversationEvalRecordDetail) {
    setActiveRecord(record);
    setRecords((current) => [
      summary(record),
      ...current.filter((item) => item.id !== record.id),
    ]);
  }

  async function executeRecord(
    recordId: number, candidate: string,
  ): Promise<void> {
    await streamConversationEvalRecordRun(recordId, candidate, {
      onDelta: (text) => setLiveOutput((current) => current + text),
      onDone: (run) => {
        setActiveRecord((current) => current?.id === recordId ? {
          ...current,
          runs: [run, ...current.runs.filter((item) => item.id !== run.id)],
        } : current);
      },
    });
    updateRecord(await getConversationEvalRecord(recordId));
  }

  async function startEvaluation() {
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
      const record = await createConversationEvalRecord(request);
      updateRecord(record);
      setView("record");
      await executeRecord(record.id, modelCandidate);
    } catch (runError) {
      setError(message(runError));
    } finally {
      setRunning(false);
      setLiveOutput("");
    }
  }

  async function runAgain() {
    if (!activeRecord || running) return;
    setRunning(true);
    setLiveOutput("");
    setError("");
    try {
      await executeRecord(activeRecord.id, modelCandidate);
    } catch (runError) {
      setError(message(runError));
    } finally {
      setRunning(false);
      setLiveOutput("");
    }
  }

  async function openRecord(recordId: number) {
    setLoading(true);
    setError("");
    try {
      setActiveRecord(await getConversationEvalRecord(recordId));
      setView("record");
    } catch (loadError) {
      setError(message(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function refreshRecord() {
    if (!activeRecord) return;
    setLoading(true);
    setError("");
    try {
      updateRecord(await getConversationEvalRecord(activeRecord.id));
    } catch (loadError) {
      setError(message(loadError));
    } finally {
      setLoading(false);
    }
  }

  if (view === "archive") {
    return (
      <ConversationEvalArchiveList
        records={records}
        hasMore={archiveHasMore}
        loading={loadingArchive}
        loadingMore={loadingMoreArchive}
        error={error}
        onOpen={(recordId) => void openRecord(recordId)}
        onNew={() => setView("launcher")}
        onRefresh={() => void refreshArchive()}
        onLoadMore={() => void loadMoreRecords()}
      />
    );
  }

  if (view === "record" && activeRecord) {
    return (
      <ConversationEvalRecordView
        record={activeRecord}
        modelCandidates={workspace?.model_candidates ?? []}
        modelCandidate={modelCandidate}
        running={running}
        liveOutput={liveOutput}
        error={error}
        onBack={() => setView("archive")}
        onRunAgain={() => void runAgain()}
        onModelCandidateChange={setModelCandidate}
        onRefresh={() => void refreshRecord()}
      />
    );
  }

  const emptyWorkspace: ConversationEvalWorkspace = {
    model_candidates: [], rounds: [], releases: [], prompt_versions: [],
    has_more: false,
  };

  return (
    <ConversationEvalView
      workspace={workspace ?? emptyWorkspace}
      detail={detail}
      selectedTurn={selectedTurn}
      promptChoice={promptChoice}
      modelCandidate={modelCandidate}
      customName={customName}
      customContent={customContent}
      archiveCount={records.length}
      loading={loading}
      running={running}
      savingPrompt={savingPrompt}
      error={error}
      onSelectRound={(turn) => {
        if (workspace && turn !== selectedTurn && !running) {
          void selectRound(turn, workspace);
        }
      }}
      onPromptChoiceChange={(choice) => {
        setPromptChoice(choice);
        if (choice === "new" && !customContent) {
          setCustomContent(detail?.original_system_prompt ?? "");
        }
      }}
      onModelCandidateChange={setModelCandidate}
      onCustomNameChange={setCustomName}
      onCustomContentChange={setCustomContent}
      onSavePrompt={() => void savePrompt()}
      onStartEvaluation={() => void startEvaluation()}
      onOpenArchive={() => {
        setView("archive");
        void refreshArchive();
      }}
      onLoadMore={() => void loadMoreSources()}
      onRefresh={() => void loadInitial(selectedTurn)}
      loadingMore={loadingMore}
    />
  );
}
