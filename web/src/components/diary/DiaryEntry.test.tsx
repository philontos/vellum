import { createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { DiaryCard } from "../../api/client";
import { I18nProvider } from "../../i18n";
import { DiaryEntry } from "./DiaryEntry";

const entry: DiaryCard = {
  id: 42,
  start_turn: 10,
  end_turn: 14,
  content: "A remembered conversation",
  created_at: "2026-07-15 09:30:00",
  stream: "neutral",
};

describe("DiaryEntry", () => {
  it("uses a compact reader header with an accessible icon-only back action", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <DiaryEntry
          card={entry}
          state={{ status: "ready", messages: [] }}
          lang="en"
          scrollRef={createRef<HTMLDivElement>()}
          onBack={() => undefined}
          onRetry={() => undefined}
        />
      </I18nProvider>,
    );

    const header = html.match(/<header[\s\S]*?<\/header>/)?.[0] ?? "";
    expect(header).not.toBe("");
    expect(header).toContain('aria-label="Back"');
    expect(header).toContain('title="Back"');
    expect(header).toContain('aria-hidden="true"');
    expect(header).toContain("absolute left-0");
    expect(header).toContain("h-10 w-10");
    expect(header).not.toContain(">Back</button>");
    expect(header).toContain("max-w-[58rem]");
    expect(header).toContain("text-center");
    expect(header).toMatch(/<h1[^>]*tabindex="-1"/);
    expect(header).not.toContain("border-l border-line pl-3");
  });
});
