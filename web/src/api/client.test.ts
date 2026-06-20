import { afterEach, describe, expect, it, vi } from "vitest";
import { getHistory, getDiary, getDiaryMessages, streamChat, streamEvalRun } from "./client";

/** Stub fetch with a JSON body; captures the requested URLs for assertions. */
function stubJson(body: unknown): string[] {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      urls.push(url);
      return { ok: true, json: async () => body } as unknown as Response;
    }),
  );
  return urls;
}

/** A fake fetch Response whose body streams the given string chunks, then ends. */
function streamResponse(chunks: string[]): Response {
  const enc = new TextEncoder();
  let i = 0;
  const reader = {
    read: async () =>
      i < chunks.length
        ? { value: enc.encode(chunks[i++]), done: false }
        : { value: undefined, done: true },
    cancel: async () => {},
    releaseLock: () => {},
  };
  return { ok: true, body: { getReader: () => reader } } as unknown as Response;
}

/** A fake fetch Response whose stream never produces data (a silently dead TCP). */
function stalledResponse(onSignal: (s: AbortSignal | undefined) => void) {
  return (_url: string, init?: { signal?: AbortSignal }) => {
    onSignal(init?.signal);
    const reader = {
      read: () => new Promise<never>(() => {}), // never resolves
      cancel: async () => {},
      releaseLock: () => {},
    };
    return Promise.resolve({ ok: true, body: { getReader: () => reader } } as unknown as Response);
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("getHistory", () => {
  it("loads the recent tail by default", async () => {
    const urls = stubJson({ messages: [{ turn: 0, role: "user", content: "hi" }] });
    const msgs = await getHistory();
    expect(urls[0]).toBe("/history?limit=200");
    expect(msgs).toEqual([{ turn: 0, role: "user", content: "hi" }]);
  });

  it("passes before= for scroll-up paging", async () => {
    const urls = stubJson({ messages: [] });
    await getHistory({ before: 12, limit: 30 });
    expect(urls[0]).toBe("/history?limit=30&before=12");
  });
});

describe("getDiary", () => {
  it("lists cards (default page) and returns them", async () => {
    const urls = stubJson({ cards: [{ id: 3, start_turn: 0, end_turn: 5, content: "x", created_at: "2026-06-20" }] });
    const cards = await getDiary();
    expect(urls[0]).toBe("/diary?limit=20");
    expect(cards[0].id).toBe(3);
  });

  it("passes before= for keyset paging", async () => {
    const urls = stubJson({ cards: [] });
    await getDiary(7);
    expect(urls[0]).toBe("/diary?limit=20&before=7");
  });
});

describe("getDiaryMessages", () => {
  it("fetches a card's span detail", async () => {
    const urls = stubJson({ summary: { id: 7 }, messages: [{ turn: 1, role: "user", content: "a" }] });
    const detail = await getDiaryMessages(7);
    expect(urls[0]).toBe("/diary/7");
    expect(detail.messages).toHaveLength(1);
  });
});

describe("streamChat", () => {
  it("calls onDelta for each chunk and resolves on [DONE]", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      streamResponse(['data: {"delta":"Hel"}\n\n', 'data: {"delta":"lo"}\n\ndata: [DONE]\n\n']),
    ));
    const got: string[] = [];
    await streamChat("hi", { onDelta: (t) => got.push(t) });
    expect(got.join("")).toBe("Hello");
  });

  it("routes reasoning and tool frames to their handlers", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      streamResponse([
        'data: {"reasoning":"thinking"}\n\n',
        'data: {"tool":{"phase":"start","name":"web_search","query":"X"}}\n\n',
        'data: {"tool":{"phase":"end","name":"web_search","ok":true}}\n\n',
        'data: {"delta":"answer"}\n\ndata: [DONE]\n\n',
      ]),
    ));
    const reasoning: string[] = [];
    const tools: unknown[] = [];
    const got: string[] = [];
    await streamChat("hi", {
      onDelta: (t) => got.push(t),
      onReasoning: (r) => reasoning.push(r),
      onTool: (ev) => tools.push(ev),
    });
    expect(reasoning.join("")).toBe("thinking");
    expect(tools).toEqual([
      { phase: "start", name: "web_search", query: "X" },
      { phase: "end", name: "web_search", ok: true },
    ]);
    expect(got.join("")).toBe("answer");
  });

  it("throws when the server sends an error frame", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      streamResponse(['data: {"delta":"partial"}\n\ndata: {"error":"provider exploded"}\n\ndata: [DONE]\n\n']),
    ));
    await expect(streamChat("hi", { onDelta: () => {} })).rejects.toThrow(/provider exploded/);
  });

  it("aborts and rejects when the stream stalls past the idle timeout", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn(stalledResponse((s) => (signal = s))));

    const p = streamChat("hi", { onDelta: () => {} }, { idleTimeoutMs: 1000 });
    const assertion = expect(p).rejects.toThrow(/timed out/i);
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
    expect(signal?.aborted).toBe(true);
  });
});

describe("streamEvalRun", () => {
  it("aborts and rejects when the run stalls past the idle timeout", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn(stalledResponse((s) => (signal = s))));

    const p = streamEvalRun("traits", {}, { idleTimeoutMs: 1000 });
    const assertion = expect(p).rejects.toThrow(/timed out/i);
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
    expect(signal?.aborted).toBe(true);
  });
});
