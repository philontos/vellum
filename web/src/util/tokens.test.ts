import { describe, expect, it } from "vitest";
import { approxTokens, charCount } from "./tokens";

describe("charCount", () => {
  it("counts code points, so CJK chars count as one each", () => {
    expect(charCount("你好")).toBe(2);
    expect(charCount("hello")).toBe(5);
    expect(charCount("")).toBe(0);
  });
});

describe("approxTokens", () => {
  it("is zero for empty text", () => {
    expect(approxTokens("")).toBe(0);
  });
  it("charges Latin text at ~4 chars per token", () => {
    expect(approxTokens("hello world")).toBe(3); // 11 chars / 4 ≈ 3
  });
  it("charges each CJK character as ~1 token", () => {
    expect(approxTokens("你好世界")).toBe(4);
  });
  it("blends CJK and Latin", () => {
    expect(approxTokens("hi 你好")).toBe(3); // 2 CJK + 3 latin/4 → round(2.75)
  });
});
