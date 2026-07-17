import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { TraceSummary } from "../api/client";
import { I18nProvider } from "../i18n";
import { TracesPanelView } from "./TracesPanel";

const trace: TraceSummary = {
  id: 7,
  turn: 3,
  stage: "chat",
  model: "m",
  prompt_tokens: 10,
  completion_tokens: 20,
  duration_ms: 30,
  pinned: 0,
  note: null,
  created_at: "2026-07-17 12:00:00",
  params: null,
  snippet: "A visible question",
  has_reasoning: true,
  has_tool_calls: false,
};

function renderView(props: Partial<React.ComponentProps<typeof TracesPanelView>> = {}) {
  return renderToStaticMarkup(
    <I18nProvider>
      <TracesPanelView
        rows={[]}
        tab="rounds"
        loading={false}
        error=""
        onTabChange={() => undefined}
        onRefresh={() => undefined}
        onPin={() => undefined}
        onNote={() => undefined}
        {...props}
      />
    </I18nProvider>,
  );
}

describe("TracesPanelView", () => {
  it("shows loading instead of a false empty state during the first request", () => {
    const html = renderView({ loading: true });

    expect(html).toContain("Loading traces");
    expect(html).not.toContain("No traces yet");
  });

  it("surfaces load failures with a retry action", () => {
    const html = renderView({ error: "traces failed: 500" });

    expect(html).toContain('role="alert"');
    expect(html).toContain("Couldn&#x27;t load traces");
    expect(html).toContain("Try again");
  });

  it("renders a lightweight round summary without heavy content", () => {
    const html = renderView({ rows: [trace] });

    expect(html).toContain("A visible question");
    expect(html).toContain("1 round");
    expect(html).not.toContain("No traces yet");
  });
});
