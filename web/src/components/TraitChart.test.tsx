import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { TraitDim } from "../api/client";
import { I18nProvider } from "../i18n";
import { TraitChart } from "./TraitChart";


describe("TraitChart", () => {
  it("shows the exact user evidence behind recent trait observations", () => {
    const dimension: TraitDim = {
      dimension: "ocean",
      content_json: { O: { score: 72 } },
      sample_count: 1,
      updated_at: "2026-07-18",
      history: [],
      meta: {
        name: "Big Five", label: "OCEAN", sort_by_score: false,
        sub_dimensions: [{ key: "O", name: "Openness" }],
      },
      observations: [{
        id: 1, dimension: "ocean", sub_dimension: "O",
        start_turn: 4, end_turn: 8, score: 82, confidence: 0.7,
        evidence_turn: 6, evidence_quote: "我喜欢尝试陌生方法",
        created_at: "2026-07-18",
      }],
    };

    const html = renderToStaticMarkup(
      <I18nProvider><TraitChart dim={dimension} /></I18nProvider>,
    );

    expect(html).toContain("Grounded signals");
    expect(html).toContain("turn 6");
    expect(html).toContain("我喜欢尝试陌生方法");
  });
});
