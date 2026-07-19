import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ModelView } from "../../api/client";
import { ConfirmProvider } from "../../confirm/ConfirmProvider";
import { I18nProvider } from "../../i18n";
import { ModelSections } from "./ModelSections";

const model: ModelView = {
  dossier: "portrait",
  current_states: [{
    id: 3,
    stream: "neutral",
    user_turn: 12,
    inquiry_id: 4,
    snapshot: {
      states: [{
        dimension: "belief",
        text: "对当前公司的信心正在下降",
        evidence: [{ turn: 12, quote: "越来越没信心" }],
      }],
      deltas: [{
        dimension: "belief",
        text: "比上次更失望",
        reference: "previous_episode",
        evidence: [{ turn: 12, quote: "比上次更失望" }],
      }],
    },
    run_id: "run-3",
    created_at: "2026-07-19 12:00:00",
  }],
  portrait_claims: [{
    id: 2,
    claim_type: "decision_style",
    text: "Seeks fair analysis before deciding.",
    basis: "explicit",
    evidence: [{ turn: 8, quote: "be a consultant, not a weather vane" }],
    status: "active",
    source_turn: 8,
  }],
  facts: [{ id: 1, text: "fact", status: "active", source_turn: 1 }],
  traits: [],
};

function sectionTag(html: string, id: string) {
  return html.match(new RegExp(`<section(?=[^>]*id="${id}")[^>]*>`))?.[0] ?? "";
}

describe("ModelSections", () => {
  it("keeps inactive sections hidden at every viewport size", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConfirmProvider>
          <ModelSections
            model={model}
            active="facts"
            onFactSave={async () => undefined}
            onFactDelete={async () => undefined}
          />
        </ConfirmProvider>
      </I18nProvider>,
    );

    expect(sectionTag(html, "model-panel-dossier")).toContain('hidden=""');
    expect(sectionTag(html, "model-panel-state")).toContain('hidden=""');
    expect(sectionTag(html, "model-panel-evidence")).toContain('hidden=""');
    expect(sectionTag(html, "model-panel-facts")).not.toContain("hidden");
    expect(sectionTag(html, "model-panel-traits")).toContain('hidden=""');
    expect(html).not.toContain("lg:block");
    expect(html).toContain("Edit fact");
    expect(html).toContain("Delete fact");
  });

  it("shows time-sensitive state separately from durable personality", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConfirmProvider>
          <ModelSections
            model={model}
            active="state"
            onFactSave={async () => undefined}
            onFactDelete={async () => undefined}
          />
        </ConfirmProvider>
      </I18nProvider>,
    );

    expect(sectionTag(html, "model-panel-state")).not.toContain("hidden");
    expect(html).toContain("对当前公司的信心正在下降");
    expect(html).toContain("比上次更失望");
    expect(html).toContain("previous episode");
    expect(html).toContain("越来越没信心");
  });

  it("shows the grounded portrait claims and their user evidence", () => {
    const html = renderToStaticMarkup(
      <I18nProvider>
        <ConfirmProvider>
          <ModelSections
            model={model}
            active="evidence"
            onFactSave={async () => undefined}
            onFactDelete={async () => undefined}
          />
        </ConfirmProvider>
      </I18nProvider>,
    );

    expect(sectionTag(html, "model-panel-evidence")).not.toContain("hidden");
    expect(html).toContain("Seeks fair analysis before deciding.");
    expect(html).toContain("decision style");
    expect(html).toContain("explicit");
    expect(html).toContain("turn 8");
    expect(html).toContain("be a consultant, not a weather vane");
  });
});
