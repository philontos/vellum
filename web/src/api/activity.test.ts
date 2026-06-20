import { describe, it, expect } from "vitest";
import { applyTool, type ActivityItem } from "./activity";

describe("applyTool", () => {
  it("appends a running item on start", () => {
    expect(applyTool(undefined, { phase: "start", name: "web_search", query: "X" })).toEqual([
      { name: "web_search", query: "X", status: "running" },
    ]);
  });

  it("marks the matching running item done on end", () => {
    const a: ActivityItem[] = [{ name: "web_search", query: "X", status: "running" }];
    expect(applyTool(a, { phase: "end", name: "web_search", ok: true })).toEqual([
      { name: "web_search", query: "X", status: "done" },
    ]);
  });

  it("marks error when ok is false", () => {
    const a: ActivityItem[] = [{ name: "web_search", query: "X", status: "running" }];
    expect(applyTool(a, { phase: "end", name: "web_search", ok: false })).toEqual([
      { name: "web_search", query: "X", status: "error" },
    ]);
  });

  it("end with no matching running item leaves the list unchanged", () => {
    expect(applyTool([], { phase: "end", name: "web_search", ok: true })).toEqual([]);
  });

  it("does not mutate the input array", () => {
    const a: ActivityItem[] = [{ name: "web_search", query: "X", status: "running" }];
    applyTool(a, { phase: "end", name: "web_search", ok: true });
    expect(a[0].status).toBe("running");
  });

  it("tracks two sequential searches independently", () => {
    let a = applyTool(undefined, { phase: "start", name: "web_search", query: "A" });
    a = applyTool(a, { phase: "end", name: "web_search", ok: true });
    a = applyTool(a, { phase: "start", name: "web_search", query: "B" });
    expect(a).toEqual([
      { name: "web_search", query: "A", status: "done" },
      { name: "web_search", query: "B", status: "running" },
    ]);
  });
});
