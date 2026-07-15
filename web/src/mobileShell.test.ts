import { describe, expect, it } from "vitest";

import appHtml from "../index.html?raw";
// Vitest runs this suite in Node; the application intentionally has no Node runtime dependency.
// @ts-expect-error Node's built-in module types are not part of the browser tsconfig.
import { readFileSync } from "node:fs";

const appCss = readFileSync(new URL("./index.css", import.meta.url), "utf8");

describe("mobile web app shell", () => {
  it("uses the full iOS viewport with an immersive standalone status bar", () => {
    expect(appHtml).toContain("viewport-fit=cover");
    expect(appHtml).toContain('<meta name="theme-color" content="#161009" />');
    expect(appHtml).toContain('<meta name="mobile-web-app-capable" content="yes" />');
    expect(appHtml).toContain('<meta name="apple-mobile-web-app-capable" content="yes" />');
    expect(appHtml).toContain(
      '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />',
    );
  });

  it("keeps the document background aligned with the mobile chrome", () => {
    expect(appCss).toContain("--v-shell-color: #161009;");
    expect(appCss).toMatch(
      /html,\s*body,\s*#root\s*\{[^}]*background-color:\s*var\(--v-shell-color\)/s,
    );
  });
});
