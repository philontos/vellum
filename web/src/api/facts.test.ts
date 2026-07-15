import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteFact, FactMutationError, updateFact } from "./facts";


afterEach(() => vi.unstubAllGlobals());


describe("manual Fact API", () => {
  it("patches a Fact and returns its active replacement", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return {
        ok: true,
        json: async () => ({
          fact: { id: 9, text: "clearer", status: "active", source_turn: 4 },
        }),
      } as Response;
    }));

    const fact = await updateFact(3, "clearer");

    expect(fact.id).toBe(9);
    expect(calls[0].url).toBe("/facts/3");
    expect(calls[0].init?.method).toBe("PATCH");
    expect(calls[0].init?.headers).toEqual({ "Content-Type": "application/json" });
    expect(calls[0].init?.body).toBe(JSON.stringify({ text: "clearer" }));
  });

  it("deletes a Fact by id", async () => {
    const calls: Array<{ url: string; method?: string }> = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, method: init?.method });
      return { ok: true, json: async () => ({ ok: true, deleted: true }) } as Response;
    }));

    await deleteFact(8);

    expect(calls[0]).toEqual({ url: "/facts/8", method: "DELETE" });
  });

  it("surfaces mutation failures", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: false, status: 409 }) as Response));

    await expect(updateFact(1, "duplicate")).rejects.toMatchObject({
      name: "FactMutationError",
      status: 409,
    });
    await expect(updateFact(1, "duplicate")).rejects.toBeInstanceOf(FactMutationError);
    await expect(deleteFact(1)).rejects.toThrow(/delete fact failed: 409/);
  });
});
