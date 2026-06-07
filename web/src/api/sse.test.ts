import { describe, it, expect } from "vitest";
import { splitFrames, parseData } from "./sse";

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
