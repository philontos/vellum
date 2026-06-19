import { describe, expect, it } from "vitest";
import { isValidElement } from "react";
import { parseBlocks, renderInline } from "./Markdown";

describe("parseBlocks", () => {
  it("splits blank-line-separated paragraphs", () => {
    const b = parseBlocks("first line\n\nsecond para");
    expect(b).toEqual([
      { type: "p", text: "first line" },
      { type: "p", text: "second para" },
    ]);
  });

  it("treats a whole-line bold span as a section heading", () => {
    const b = parseBlocks("**一、是不是应该盘点团队？**");
    expect(b).toEqual([{ type: "heading", level: 4, text: "一、是不是应该盘点团队？" }]);
  });

  it("keeps a bold lead-in inside a paragraph (not a heading)", () => {
    const src = "**第一层：你能识别。** 用户体验的最后一公里。";
    expect(parseBlocks(src)).toEqual([{ type: "p", text: src }]);
  });

  it("does not mistake two bold spans on one line for a heading", () => {
    const b = parseBlocks("**a** and **b**");
    expect(b).toEqual([{ type: "p", text: "**a** and **b**" }]);
  });

  it("reads ATX headings with levels", () => {
    expect(parseBlocks("## Title")).toEqual([{ type: "heading", level: 2, text: "Title" }]);
  });

  it("groups consecutive bullets into one list and stops cleanly", () => {
    const b = parseBlocks("- one\n- two\n\nafter");
    expect(b).toEqual([
      { type: "ul", items: ["one", "two"] },
      { type: "p", text: "after" },
    ]);
  });

  it("groups numbered items into an ordered list", () => {
    expect(parseBlocks("1. a\n2. b")).toEqual([{ type: "ol", items: ["a", "b"] }]);
  });

  it("reads --- as a horizontal rule between paragraphs", () => {
    const b = parseBlocks("before\n\n---\n\nafter");
    expect(b).toEqual([
      { type: "p", text: "before" },
      { type: "hr" },
      { type: "p", text: "after" },
    ]);
  });

  it("renders a bold span as a <strong> between text runs", () => {
    const out = renderInline("x **y** z", "k");
    expect(out).toHaveLength(3);
    const strong = out[1];
    expect(isValidElement(strong) && strong.type).toBe("strong");
  });

  it("terminates on emphasis nested inside bold (the recursive case)", () => {
    // A shared stateful /g regex would loop forever here — this must return fast.
    expect(() => renderInline("**outer *inner* and `code`** tail", "k")).not.toThrow();
    const out = renderInline("**a *b* `c`**", "k");
    expect(Array.isArray(out)).toBe(true);
    expect(isValidElement(out[0]) && out[0].type).toBe("strong");
  });

  it("never loops on a long bullet run", () => {
    const src = Array.from({ length: 50 }, (_, i) => `- item ${i}`).join("\n");
    const b = parseBlocks(src);
    expect(b).toHaveLength(1);
    expect(b[0]).toMatchObject({ type: "ul" });
    expect((b[0] as { items: string[] }).items).toHaveLength(50);
  });
});
