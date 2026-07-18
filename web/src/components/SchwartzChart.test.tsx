import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SchwartzProfile, TraitDim } from "../api/client";
import { I18nProvider } from "../i18n";
import { SchwartzChart } from "./SchwartzChart";
import { SCHWARTZ_KEYS } from "./schwartz/model";

function trait(): TraitDim {
  const values = Object.fromEntries(SCHWARTZ_KEYS.map((key, index) => [key, {
    priority: key === "tradition" ? null : (4 - index) / 20,
    interval: key === "tradition" ? null : [-0.1, 0.3] as [number, number],
    confidence: key === "tradition" ? 0 : 0.6,
    stance: key === "tradition" ? "unobserved" as const : "support" as const,
    explicit_opposition: false,
    evidence_count: key === "tradition" ? 0 : 2,
    effective_evidence: key === "tradition" ? 0 : 0.8,
    activation: key === "self_direction" ? 0.8 : 0.1,
    status: key === "tradition" ? "unobserved" as const : "context_dependent" as const,
    evidence: key === "self_direction" ? "I chose autonomy" : null,
    latest_evidence: key === "self_direction" ? [{
      quote: "I chose autonomy", direction: "support" as const, basis: "tradeoff",
      counterpart: "security", start_turn: 10, end_turn: 14,
    }] : [],
  }])) as SchwartzProfile["values"];
  return {
    dimension: "schwartz", content_json: {}, sample_count: 41, updated_at: "",
    history: [], meta: null,
    profile: {
      kind: "schwartz_circumplex", model_version: "schwartz-v2",
      calibration: "conversation_evidence",
      scale: { minimum: -1, center: 0, maximum: 1, meaning: "within_person_relative_priority" },
      coverage: { assessed: 9, total: 10, evidence_count: 18 }, values,
      axes: [
        { key: "openness_conservation", left: "openness_to_change", right: "conservation", score: -0.25, confidence: 0.6 },
        { key: "transcendence_enhancement", left: "self_transcendence", right: "self_enhancement", score: 0.1, confidence: 0.5 },
      ],
    },
  };
}

describe("SchwartzChart", () => {
  it("renders the complete circumplex, centered scale, axes, and evidence detail", () => {
    const html = renderToStaticMarkup(
      <I18nProvider><SchwartzChart dim={trait()} /></I18nProvider>,
    );

    expect(html).toContain("Schwartz Basic Values");
    expect(html).toContain("9/10 assessed");
    expect(html).toContain("0 = your own average");
    expect(html).toContain("Self-Direction");
    expect(html).toContain("Tradition");
    expect(html).toContain("Not enough evidence");
    expect(html).toContain("Openness to change");
    expect(html).toContain("Conservation");
    expect(html).toContain("I chose autonomy");
    expect(html).not.toContain("41 samples");
  });
});
