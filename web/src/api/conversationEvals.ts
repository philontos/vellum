import { splitFrames } from "./sse";

export type ConversationEvalRound = {
  user_turn: number;
  assistant_turn: number;
  stream: string;
  user_content: string;
  original_content: string;
  created_at: string;
  trace_id: number | null;
  prompt_release_id: number | null;
  prompt_release_version: number | null;
  model: string | null;
  replayable: boolean;
};

export type ConversationPromptRelease = {
  id: number;
  version: number;
  note: string;
  published_at: string;
  is_active: boolean;
};

export type ConversationPromptVersion = {
  id: number;
  name: string;
  content: string;
  created_at: string;
};

export type ConversationModelCandidate = {
  id: string;
  name: string;
  model: string;
  configured: boolean;
};

export type ConversationEvalRun = {
  id: number;
  record_id: number | null;
  source_user_turn: number;
  source_assistant_turn: number;
  stream: string;
  prompt_kind: "original" | "release" | "custom";
  prompt_release_id: number | null;
  prompt_release_version: number | null;
  prompt_version_id: number | null;
  prompt_label: string;
  model: string | null;
  status: "running" | "done" | "error";
  output: string | null;
  error: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  duration_ms: number | null;
  created_at: string;
  finished_at: string | null;
};

export type ConversationEvalWorkspace = {
  model_candidates: ConversationModelCandidate[];
  default_model_candidate: string;
  rounds: ConversationEvalRound[];
  releases: ConversationPromptRelease[];
  prompt_versions: ConversationPromptVersion[];
  has_more: boolean;
};

export type ConversationEvalRoundDetail = {
  round: ConversationEvalRound;
  original_system_prompt: string | null;
};

export type ConversationPromptMessage = {
  role: string;
  content: string;
  name?: string;
};

export type ConversationEvalRecordSummary = {
  id: number;
  source_user_turn: number;
  source_assistant_turn: number;
  stream: string;
  source_user_content: string;
  baseline_output: string;
  baseline_prompt_label: string;
  prompt_kind: "original" | "release" | "custom";
  prompt_release_id: number | null;
  prompt_release_version: number | null;
  prompt_version_id: number | null;
  prompt_label: string;
  run_count: number;
  latest_status: ConversationEvalRun["status"] | null;
  latest_output: string | null;
  created_at: string;
};

export type ConversationEvalRecordDetail = ConversationEvalRecordSummary & {
  source_created_at: string | null;
  baseline_prompt_release_id: number | null;
  baseline_prompt_release_version: number | null;
  baseline_system_prompt: string | null;
  baseline_input: ConversationPromptMessage[] | null;
  system_prompt: string;
  input: ConversationPromptMessage[];
  runs: ConversationEvalRun[];
};

export type ConversationEvalRecordPage = {
  records: ConversationEvalRecordSummary[];
  has_more: boolean;
};

export type ConversationEvalRunRequest = {
  assistant_turn: number;
  prompt_kind: "original" | "release" | "custom";
  prompt_release_id?: number;
  prompt_version_id?: number;
  model_candidate?: string;
};

type ConversationEvalRecordRunRequest = {
  model_candidate: string;
};

async function responseError(response: Response, action: string): Promise<Error> {
  try {
    const body = await response.json() as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail) return new Error(body.detail);
  } catch {
    // Status fallback below handles empty and non-JSON responses.
  }
  return new Error(`${action} failed: ${response.status}`);
}

export async function getConversationEvalWorkspace(
  opts: { limit?: number; before?: number } = {},
): Promise<ConversationEvalWorkspace> {
  const query = new URLSearchParams({ limit: String(opts.limit ?? 50) });
  if (opts.before !== undefined) query.set("before", String(opts.before));
  const response = await fetch(`/inspect/conversation-evals?${query}`, {
    cache: "no-store",
  });
  if (!response.ok) throw await responseError(response, "load conversation evals");
  return response.json();
}

export async function getConversationEvalRound(
  assistantTurn: number,
): Promise<ConversationEvalRoundDetail> {
  const response = await fetch(
    `/inspect/conversation-evals/rounds/${assistantTurn}`,
    { cache: "no-store" },
  );
  if (!response.ok) throw await responseError(response, "load conversation round");
  return response.json();
}

export async function getConversationEvalRecords(
  opts: { limit?: number; before?: number } = {},
): Promise<ConversationEvalRecordPage> {
  const query = new URLSearchParams({ limit: String(opts.limit ?? 50) });
  if (opts.before !== undefined) query.set("before", String(opts.before));
  const response = await fetch(`/inspect/conversation-evals/records?${query}`, {
    cache: "no-store",
  });
  if (!response.ok) throw await responseError(response, "load evaluation archives");
  return response.json();
}

export async function getConversationEvalRecord(
  recordId: number,
): Promise<ConversationEvalRecordDetail> {
  const response = await fetch(
    `/inspect/conversation-evals/records/${recordId}`,
    { cache: "no-store" },
  );
  if (!response.ok) throw await responseError(response, "load evaluation archive");
  return response.json();
}

export async function createConversationEvalRecord(
  request: ConversationEvalRunRequest,
): Promise<ConversationEvalRecordDetail> {
  const response = await fetch("/inspect/conversation-evals/records", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw await responseError(response, "create evaluation archive");
  return response.json();
}

export async function createConversationPromptVersion(
  name: string,
  content: string,
): Promise<ConversationPromptVersion> {
  const response = await fetch("/inspect/conversation-evals/prompt-versions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, content }),
  });
  if (!response.ok) throw await responseError(response, "save Prompt version");
  return response.json();
}

type RunHandlers = {
  onRun?: (run: ConversationEvalRun) => void;
  onDelta?: (text: string) => void;
  onActivity?: (activity: Record<string, unknown>) => void;
  onDone?: (run: ConversationEvalRun) => void;
};

function parseFrame(frame: string): {
  kind: "run" | "delta" | "activity" | "done" | "end";
  data?: unknown;
} | null {
  const line = frame.split("\n").find((part) => part.startsWith("data:"));
  if (!line) return null;
  const payload = line.slice(5).trim();
  if (payload === "[DONE]") return { kind: "end" };
  try {
    const value = JSON.parse(payload) as Record<string, unknown>;
    if (value.run) return { kind: "run", data: value.run };
    if (value.delta) return { kind: "delta", data: value.delta };
    if (value.activity) return { kind: "activity", data: value.activity };
    if (value.done) return { kind: "done", data: value.done };
  } catch {
    return null;
  }
  return null;
}

async function streamConversationEvalAt(
  url: string,
  request: ConversationEvalRunRequest | ConversationEvalRecordRunRequest | null,
  handlers: RunHandlers,
  opts: { idleTimeoutMs?: number } = {},
): Promise<void> {
  const controller = new AbortController();
  const response = await fetch(url, {
    method: "POST",
    ...(request ? {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    } : {}),
    signal: controller.signal,
  });
  if (!response.ok || !response.body) {
    throw await responseError(response, "run conversation replay");
  }

  const timeout = opts.idleTimeoutMs ?? 120_000;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      let timer: ReturnType<typeof setTimeout> | undefined;
      const read = reader.read();
      const deadline = new Promise<never>((_, reject) => {
        timer = setTimeout(() => {
          controller.abort();
          reject(new Error(`conversation replay timed out after ${timeout}ms`));
        }, timeout);
      });
      const { value, done } = await Promise.race([read, deadline]).finally(
        () => clearTimeout(timer),
      );
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const split = splitFrames(buffer);
      buffer = split.rest;
      for (const raw of split.frames) {
        const frame = parseFrame(raw);
        if (!frame) continue;
        if (frame.kind === "end") return;
        if (frame.kind === "run") {
          handlers.onRun?.(frame.data as ConversationEvalRun);
        } else if (frame.kind === "delta") {
          const data = frame.data as { text?: unknown };
          if (typeof data.text === "string") handlers.onDelta?.(data.text);
        } else if (frame.kind === "activity") {
          handlers.onActivity?.(frame.data as Record<string, unknown>);
        } else if (frame.kind === "done") {
          handlers.onDone?.(frame.data as ConversationEvalRun);
        }
      }
    }
  } finally {
    controller.abort();
  }
}

export async function streamConversationEvalRun(
  request: ConversationEvalRunRequest,
  handlers: RunHandlers,
  opts: { idleTimeoutMs?: number } = {},
): Promise<void> {
  return streamConversationEvalAt(
    "/inspect/conversation-evals/run", request, handlers, opts,
  );
}

export async function streamConversationEvalRecordRun(
  recordId: number,
  modelCandidate: string,
  handlers: RunHandlers,
  opts: { idleTimeoutMs?: number } = {},
): Promise<void> {
  return streamConversationEvalAt(
    `/inspect/conversation-evals/records/${recordId}/runs`,
    { model_candidate: modelCandidate },
    handlers,
    opts,
  );
}
