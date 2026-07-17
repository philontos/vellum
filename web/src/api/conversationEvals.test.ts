import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createConversationPromptVersion,
  getConversationEvalRound,
  getConversationEvalWorkspace,
  streamConversationEvalRun,
} from "./conversationEvals";

afterEach(() => vi.unstubAllGlobals());

function response(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response;
}

describe("conversation eval client", () => {
  it("loads selectable historical rounds and one comparison", async () => {
    const fetchMock = vi.fn(async () => response({ rounds: [] }));
    vi.stubGlobal("fetch", fetchMock);

    await getConversationEvalWorkspace({ limit: 30, before: 80 });
    await getConversationEvalRound(81);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/inspect/conversation-evals?limit=30&before=80",
      { cache: "no-store" },
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/inspect/conversation-evals/rounds/81",
      { cache: "no-store" },
    );
  });

  it("submits a named Prompt version", async () => {
    const fetchMock = vi.fn(async () => response({ id: 4 }));
    vi.stubGlobal("fetch", fetchMock);

    await createConversationPromptVersion("Concise v2", "Match the user's language.");

    expect(fetchMock).toHaveBeenCalledWith(
      "/inspect/conversation-evals/prompt-versions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: "Concise v2",
          content: "Match the user's language.",
        }),
      },
    );
  });

  it("streams run metadata, text deltas, and the durable result", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode(
          'data: {"run":{"id":12}}\n\n' +
          'data: {"delta":{"text":"new"}}\n\n' +
          'data: {"done":{"id":12,"status":"done","output":"new"}}\n\n' +
          "data: [DONE]\n\n",
        ));
        controller.close();
      },
    });
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, status: 200, body }) as Response));
    const events: string[] = [];

    await streamConversationEvalRun(
      { assistant_turn: 9, prompt_kind: "release", prompt_release_id: 3 },
      {
        onRun: (run) => events.push(`run:${run.id}`),
        onDelta: (text) => events.push(`delta:${text}`),
        onDone: (run) => events.push(`done:${run.output}`),
      },
    );

    expect(events).toEqual(["run:12", "delta:new", "done:new"]);
  });
});
