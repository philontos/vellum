import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { I18nProvider } from "../../i18n";
import { SuiteEvalPanelView } from "./SuiteEvalPanel";


describe("SuiteEvalPanelView", () => {
  it("exposes the Inquiry regression suite and its loop-quality metrics", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <SuiteEvalPanelView
          suites={[
            { key: "inquiry", needs_eval_gen: false },
            { key: "consultant", needs_eval_gen: true },
          ]}
          runs={[{
            id: 9, suite: "inquiry", status: "done",
            model: "controller-model", eval_model: null,
            total: 6, completed: 6,
            aggregate: {
              routing_accuracy: 1,
              premature_answer_rate: 0,
              unnecessary_inquiry_rate: 0,
            },
            error: null, started_at: "2026-07-18", finished_at: "2026-07-18",
          }]}
          selectedSuite="inquiry"
          running={false}
          progress={null}
          loading={false}
          error=""
          onSuiteChange={() => undefined}
          onRun={() => undefined}
          onRefresh={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("inquiry");
    expect(html).toContain("rule-based");
    expect(html).toContain("routing accuracy");
    expect(html).toContain("premature answer rate");
    expect(html).toContain("unnecessary inquiry rate");
  });

  it("shows the structured decision and metrics for an expanded eval case", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <SuiteEvalPanelView
          suites={[{ key: "inquiry", needs_eval_gen: false }]}
          runs={[{
            id: 9, suite: "inquiry", status: "done",
            model: "controller-model", eval_model: null,
            total: 1, completed: 1, aggregate: null, error: null,
            started_at: "2026-07-18", finished_at: "2026-07-18",
          }]}
          detail={{
            run: {
              id: 9, suite: "inquiry", status: "done",
              model: "controller-model", eval_model: null,
              total: 1, completed: 1, aggregate: null, error: null,
              started_at: "2026-07-18", finished_at: "2026-07-18",
            },
            results: [{
              id: 1, run_id: 9, seq: 0, case_name: "open_high_stakes",
              status: "pass", error: null, created_at: "2026-07-18",
              result: {
                actual_route: "inquire",
                evidence_valid: true,
                decision: { operation: "open" },
              },
            }],
            traces: [],
          }}
          selectedSuite="inquiry"
          running={false}
          progress={null}
          loading={false}
          error=""
          onSuiteChange={() => undefined}
          onRun={() => undefined}
          onRefresh={() => undefined}
          onOpen={() => undefined}
        />
      </I18nProvider>,
    );

    expect(html).toContain("open_high_stakes");
    expect(html).toContain("actual_route");
    expect(html).toContain("inquire");
    expect(html).toContain("evidence_valid");
  });
});
