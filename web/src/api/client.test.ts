import { afterEach, describe, expect, it, vi } from "vitest";
import { streamChat, streamEvalRun } from "./client";

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

describe("streamChat", () => {
  it("calls onDelta for each chunk and resolves on [DONE]", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      streamResponse(['data: {"delta":"Hel"}\n\n', 'data: {"delta":"lo"}\n\ndata: [DONE]\n\n']),
    ));
    const got: string[] = [];
    await streamChat("hi", (t) => got.push(t));
    expect(got.join("")).toBe("Hello");
  });

  it("throws when the server sends an error frame", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      streamResponse(['data: {"delta":"partial"}\n\ndata: {"error":"provider exploded"}\n\ndata: [DONE]\n\n']),
    ));
    await expect(streamChat("hi", () => {})).rejects.toThrow(/provider exploded/);
  });

  it("aborts and rejects when the stream stalls past the idle timeout", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn(stalledResponse((s) => (signal = s))));

    const p = streamChat("hi", () => {}, { idleTimeoutMs: 1000 });
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
