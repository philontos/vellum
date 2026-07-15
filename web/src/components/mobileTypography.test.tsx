import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

// Vitest runs this suite in Node; the application intentionally has no Node runtime dependency.
// @ts-expect-error Node's built-in module types are not part of the browser tsconfig.
import { readFileSync } from "node:fs";
import { Markdown } from "./Markdown";

const appCss = readFileSync(new URL("../index.css", import.meta.url), "utf8");

describe("mobile assistant typography", () => {
  it("uses a smaller body size and marks CJK replies for tidy line endings", () => {
    const cjk = renderToStaticMarkup(<Markdown text="这是一段中文回复，用来验证移动端排版。" />);
    const latin = renderToStaticMarkup(<Markdown text="A concise English reply." />);

    expect(cjk).toContain(
      "v-md v-md--cjk text-[14px] font-normal leading-[1.72] sm:text-base sm:leading-[1.72]",
    );
    expect(latin).toContain(
      "v-md text-[14px] font-normal leading-[1.72] sm:text-base sm:leading-[1.72]",
    );
    expect(latin).not.toContain("v-md--cjk");
  });

  it("uses a sans reading face on mobile while preserving serif accents", () => {
    expect(appCss).toMatch(
      /\.v-md\s*\{[^}]*font-family:\s*theme\("fontFamily\.sans"\)[^}]*text-wrap:\s*wrap/s,
    );
    expect(appCss).toMatch(
      /@media \(min-width: 640px\)\s*\{\s*\.v-md\s*\{[^}]*font-family:\s*theme\("fontFamily\.serif"\)[^}]*text-wrap:\s*pretty/s,
    );
    expect(appCss).toMatch(
      /\.v-md-h\s*\{[^}]*font-family:\s*theme\("fontFamily\.serif"\)[^}]*color:\s*theme\("colors\.gold"\)/s,
    );
  });

  it("justifies only CJK prose on narrow screens", () => {
    expect(appCss).toMatch(
      /@media \(max-width: 639px\)\s*\{[^}]*\.v-md--cjk p,[^}]*\.v-md--cjk li\s*\{[^}]*text-align:\s*justify[^}]*text-justify:\s*inter-character[^}]*text-align-last:\s*start/s,
    );
  });
});
