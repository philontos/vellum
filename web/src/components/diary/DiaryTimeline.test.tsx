import { createRef } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { DiaryCard } from "../../api/client";
import { I18nProvider } from "../../i18n";
import { DiaryTimeline } from "./DiaryTimeline";

const entry: DiaryCard = {
  id: 42,
  start_turn: 10,
  end_turn: 14,
  content: "A remembered conversation",
  created_at: "2026-07-15 09:30:00",
  stream: "neutral",
};

describe("DiaryTimeline", () => {
  it("renders each entry as a real page link", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <DiaryTimeline
          days={[{ day: "2026-07-15", cards: [entry] }]}
          cardCount={1}
          stream="neutral"
          lang="en"
          loading={false}
          atEnd={false}
          scrollRef={createRef<HTMLDivElement>()}
          bottomRef={createRef<HTMLDivElement>()}
          onStreamChange={() => undefined}
          onOpen={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain('href="/app/diary/42"');
    expect(html).toContain('data-diary-card="42"');
  });
});
