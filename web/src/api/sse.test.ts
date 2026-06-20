import { describe, it, expect } from "vitest";
import { splitFrames, parseData, parseEvalFrame } from "./sse";

describe("splitFrames", () => {
  it("splits complete \\n\\n frames and keeps the remainder", () => {
    const { frames, rest } = splitFrames('data: {"delta":"hi"}\n\ndata: {"delta":"the');
    expect(frames).toEqual(['data: {"delta":"hi"}']);
    expect(rest).toBe('data: {"delta":"the');
  });
  it("returns no frames when none complete", () => {
    const { frames, rest } = splitFrames("data: partial");
    expect(frames).toEqual([]);
    expect(rest).toBe("data: partial");
  });
});

describe("parseData", () => {
  it("parses a delta frame", () => {
    expect(parseData('data: {"delta":"hello"}')).toEqual({ type: "delta", text: "hello" });
  });
  it("recognizes [DONE]", () => {
    expect(parseData("data: [DONE]")).toEqual({ type: "done" });
  });
  it("recognizes an error frame", () => {
    expect(parseData('data: {"error":"boom"}')).toEqual({ type: "error", message: "boom" });
  });
  it("ignores non-data / malformed lines", () => {
    expect(parseData(": comment")).toBeNull();
    expect(parseData("data: {not json}")).toBeNull();
  });
  it("passes through an empty delta", () => {
    expect(parseData('data: {"delta":""}')).toEqual({ type: "delta", text: "" });
  });
  it("returns null when the delta field is absent", () => {
    expect(parseData('data: {"foo":1}')).toBeNull();
  });
});

describe("parseEvalFrame", () => {
  it("parses a run frame", () => {
    expect(parseEvalFrame('data: {"run":{"id":1,"suite":"traits","total":3}}'))
      .toEqual({ kind: "run", data: { id: 1, suite: "traits", total: 3 } });
  });
  it("parses a case frame", () => {
    expect(parseEvalFrame('data: {"case":{"seq":0,"case":"ocean_O_high","status":"pass"}}'))
      .toEqual({ kind: "case", data: { seq: 0, case: "ocean_O_high", status: "pass" } });
  });
  it("parses a done frame", () => {
    expect(parseEvalFrame('data: {"done":{"status":"done","aggregate":{"pass":1}}}'))
      .toEqual({ kind: "done", data: { status: "done", aggregate: { pass: 1 } } });
  });
  it("recognizes [DONE] as end", () => {
    expect(parseEvalFrame("data: [DONE]")).toEqual({ kind: "end" });
  });
  it("ignores comments / malformed / unknown shapes", () => {
    expect(parseEvalFrame(": comment")).toBeNull();
    expect(parseEvalFrame("data: {not json}")).toBeNull();
    expect(parseEvalFrame('data: {"foo":1}')).toBeNull();
  });
});
