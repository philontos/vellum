import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { TraceSummary } from "../../api/client";
import { I18nProvider } from "../../i18n";
import { TraceRow } from "./TraceRow";

describe("TraceRow", () => {
  it("renders summary indicators before heavy detail is fetched", () => {
    const trace: TraceSummary = {
      id: 9,
      turn: 5,
      stage: "chat",
      model: "m",
      prompt_tokens: 10,
      completion_tokens: 20,
      duration_ms: 30,
      pinned: 0,
      note: null,
      created_at: "2026-07-17 12:00:00",
      params: null,
      snippet: "question",
      dimension: null,
      has_reasoning: true,
      has_tool_calls: true,
    };

    const html = renderToStaticMarkup(
      <I18nProvider>
        <TraceRow trace={trace} onPin={() => undefined} onNote={() => undefined} />
      </I18nProvider>,
    );

    expect(html).toContain("🧠");
    expect(html).toContain("🔧");
    expect(html).toContain("Expand");
    expect(html).not.toContain("PROMPT");
  });
});
