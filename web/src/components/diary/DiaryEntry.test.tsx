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
  it("renders as a responsive modal with an accessible icon-only close action", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <DiaryEntry
          card={entry}
          state={{ status: "ready", messages: [] }}
          lang="en"
          scrollRef={createRef<HTMLDivElement>()}
          onClose={() => undefined}
          onRetry={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain("absolute inset-0");
    expect(html).toContain("p-2");
    expect(html).toContain("sm:p-6");
    expect(html).toContain("h-full max-h-[48rem]");
    expect(html).toContain("max-w-[58rem]");

    const header = html.match(/<header[\s\S]*?<\/header>/)?.[0] ?? "";
    expect(header).not.toBe("");
    expect(header).toContain('aria-label="Close diary entry"');
    expect(header).toContain('title="Close diary entry"');
    expect(header).toContain('aria-hidden="true"');
    expect(header).toContain("absolute right-0");
    expect(header).toContain("h-10 w-10");
    expect(header).toContain("✕");
    expect(header).not.toContain("←");
  });
});
