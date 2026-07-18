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
  dimension: null,
  has_reasoning: true,
  has_tool_calls: false,
};

function renderView(props: Partial<React.ComponentProps<typeof TracesPanelView>> = {}) {
  return renderToStaticMarkup(
    <I18nProvider>
      <TracesPanelView
        rows={[]}
        runs={[]}
        inquiries={[]}
        tab="rounds"
        backgroundTab="all"
        loading={false}
        error=""
        onTabChange={() => undefined}
        onBackgroundTabChange={() => undefined}
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

  it("renders controller and responder stages as one visible pipeline", () => {
    const rows: TraceSummary[] = [
      {
        ...trace,
        id: 8,
        stage: "inquiry.decide",
        model: "controller-model",
        run_id: "run-1",
        scenario: "inquiry",
        attempt: 1,
      },
      {
        ...trace,
        id: 9,
        stage: "chat",
        model: "responder-model",
        run_id: "run-1",
        scenario: "chat",
        attempt: 1,
      },
    ];

    const html = renderView({ rows });

    expect(html).toContain("controller-model");
    expect(html).toContain("responder-model");
    expect(html.indexOf("controller-model")).toBeLessThan(html.indexOf("responder-model"));
  });

  it("shows the root route, revision transition, and degraded state", () => {
    const html = renderView({
      rows: [{ ...trace, run_id: "run-1" }],
      runs: [{
        id: "run-1", user_turn: 2, assistant_turn: 3,
        stream: "neutral", route: "synthesize", status: "degraded",
        inquiry_id: 4, revision_before: 2, revision_after: 3,
        controller_model: "controller", responder_model: "responder",
        decision: { route: "synthesize" }, context_meta: {
          estimated_tokens: 900, max_input_tokens: 1000,
          remaining_questions: 1, max_questions: 5,
          dropped_recent_messages: 2, dropped_cited_evidence: 1,
          current_user_turn_truncated: true,
        },
        prompt_release_id: null, prompt_release_version: null,
        error: "controller fallback", started_at: "2026-07-17 12:00:00",
        finished_at: "2026-07-17 12:00:01",
      }],
    });

    expect(html).toContain("synthesize");
    expect(html).toContain("degraded");
    expect(html).toContain("rev 2→3");
    expect(html).toContain("ctx 900/1000 tok");
    expect(html).toContain("1/5 questions left");
    expect(html).toContain("3 context items dropped");
    expect(html).toContain("current turn truncated");
  });

  it("associates a controller-only failed round with its root run", () => {
    const html = renderView({
      rows: [{
        ...trace, id: 10, turn: 2, stage: "inquiry.decide",
        run_id: "failed-run", snippet: "A failed request",
      }],
      runs: [{
        id: "failed-run", user_turn: 2, assistant_turn: null,
        stream: "neutral", route: null, status: "error",
        inquiry_id: null, revision_before: null, revision_after: null,
        controller_model: "controller", responder_model: null,
        decision: null, context_meta: {}, prompt_release_id: null,
        prompt_release_version: null, error: "responder unavailable",
        started_at: "2026-07-17 12:00:00", finished_at: "2026-07-17 12:00:01",
      }],
    });

    expect(html).toContain("A failed request");
    expect(html).toContain("error");
    expect(html).toContain("responder unavailable");
  });

  it("renders an Inquiry Ledger with evidence classes and open unknowns", () => {
    const html = renderView({
      tab: "inquiries",
      inquiries: [{
        id: 4, stream: "neutral", status: "exploring", revision: 2,
        goal: "判断是否应该辞职", opened_turn: 40, last_turn: 42,
        closed_turn: null, parent_inquiry_id: null,
        created_at: "2026-07-17 12:00:00", updated_at: "2026-07-17 12:01:00",
        ledger: {
          goal: {
            text: "判断是否应该辞职",
            evidence: [{ turn: 40, quote: "我是不是应该辞职" }],
          },
          observations: [{
            id: "o1", text: "上周收到负面反馈",
            evidence: [{ turn: 40, quote: "他在会上说我的方案不达标" }],
          }],
          interpretations: [{
            id: "i1", text: "领导可能在针对我",
            evidence: [{ turn: 40, quote: "我觉得他就是针对我" }],
          }],
          hypotheses: [{
            id: "h1", text: "正常但粗暴的绩效反馈",
            supporting_evidence: [{ turn: 41, quote: "他也批评了另外两个人" }],
            disconfirming_evidence: [{ turn: 42, quote: "只有我的任务被撤掉" }],
          }],
          blocking_unknowns: [{
            id: "u1", question: "最近具体发生了什么？",
            why_material: "区分反馈与针对", status: "open",
            resolved_after_turn: null,
          }],
          asked_questions: [{
            unknown_id: "u1", text: "请说一件最近的具体事件。", after_turn: 40,
          }],
          provisional_conclusion: null,
        },
      }],
    });

    expect(html).toContain("判断是否应该辞职");
    expect(html).toContain("上周收到负面反馈");
    expect(html).toContain("领导可能在针对我");
    expect(html).toContain("正常但粗暴的绩效反馈");
    expect(html).toContain("最近具体发生了什么？");
    expect(html).toContain("他在会上说我的方案不达标");
    expect(html).toContain("我觉得他就是针对我");
    expect(html).toContain("他也批评了另外两个人");
    expect(html).toContain("只有我的任务被撤掉");
    expect(html).toContain("我是不是应该辞职");
    expect(html).toContain("请说一件最近的具体事件。");
  });

  it("shows stable background category tabs with counts", () => {
    const rows: TraceSummary[] = [
      { ...trace, id: 8, stage: "trait", dimension: "ocean", model: "ocean-model" },
      { ...trace, id: 7, stage: "summary", model: "summary-model" },
      { ...trace, id: 6, stage: "dossier_evidence", model: "evidence-model" },
      { ...trace, id: 5, stage: "dossier_render", model: "render-model" },
    ];

    const html = renderView({ rows, tab: "background" });

    expect(html).toContain("OCEAN");
    expect(html).toContain("MBTI");
    expect(html).toContain("Values");
    expect(html).toContain("Regulatory focus");
    expect(html).toContain("Summary");
    expect(html).toContain("Dossier evidence");
    expect(html).toContain("Dossier render");
    expect(html).toContain("Fact cleanup");
  });

  it("renders only the selected background category", () => {
    const rows: TraceSummary[] = [
      { ...trace, id: 8, stage: "trait", dimension: "ocean", model: "ocean-model" },
      { ...trace, id: 7, stage: "summary", model: "summary-model" },
    ];

    const html = renderView({ rows, tab: "background", backgroundTab: "summary" });

    expect(html).toContain("summary-model");
    expect(html).not.toContain("ocean-model");
  });

  it("shows legacy dossier rows together with the new render stage", () => {
    const rows: TraceSummary[] = [
      { ...trace, id: 9, stage: "dossier_render", model: "new-render" },
      { ...trace, id: 8, stage: "dossier", model: "legacy-render" },
      { ...trace, id: 7, stage: "dossier_evidence", model: "evidence" },
    ];

    const html = renderView({
      rows,
      tab: "background",
      backgroundTab: "dossier_render",
    });

    expect(html).toContain("new-render");
    expect(html).toContain("legacy-render");
    expect(html).not.toContain(">evidence<");
  });
});
