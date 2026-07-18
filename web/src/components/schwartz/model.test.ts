import { describe, expect, it } from "vitest";

import type { SchwartzProfile, TraitDim } from "../../api/client";
import {
  SCHWARTZ_KEYS,
  circumplexPoint,
  legacySchwartzProfile,
  schwartzValues,
  summarizeValues,
} from "./model";

function profile(): SchwartzProfile {
  const values = Object.fromEntries(SCHWARTZ_KEYS.map((key) => [key, {
    priority: key === "tradition" ? null : 0,
    interval: key === "tradition" ? null : [-0.2, 0.2],
    confidence: key === "tradition" ? 0 : 0.5,
    stance: key === "tradition" ? "unobserved" : "support",
    explicit_opposition: false,
    evidence_count: key === "tradition" ? 0 : 2,
    effective_evidence: key === "tradition" ? 0 : 0.8,
    activation: 0,
    status: key === "tradition" ? "unobserved" : "context_dependent",
    evidence: null,
    latest_evidence: [],
  }])) as unknown as SchwartzProfile["values"];
  values.self_direction = {
    ...values.self_direction,
    priority: 0.42,
    interval: [0.18, 0.61],
    status: "core_priority",
  };
  values.security = {
    ...values.security,
    priority: -0.31,
    interval: [-0.5, -0.12],
    stance: "yielding",
    status: "relative_yielding",
  };
  return {
    kind: "schwartz_circumplex",
    model_version: "schwartz-v2",
    calibration: "conversation_evidence",
    scale: { minimum: -1, center: 0, maximum: 1, meaning: "within_person_relative_priority" },
    coverage: { assessed: 9, total: 10, evidence_count: 18 },
    values,
    axes: [
      { key: "openness_conservation", left: "openness_to_change", right: "conservation", score: -0.32, confidence: 0.5 },
      { key: "transcendence_enhancement", left: "self_transcendence", right: "self_enhancement", score: 0.12, confidence: 0.4 },
    ],
  };
}

function dim(p: Partial<TraitDim> = {}): TraitDim {
  return {
    dimension: "schwartz", content_json: {}, sample_count: 41,
    updated_at: "", history: [], meta: null, profile: profile(), ...p,
  };
}

describe("Schwartz presentation model", () => {
  it("always follows the fixed motivational-circle order and keeps unobserved values", () => {
    const values = schwartzValues(dim());
    expect(values.map((value) => value.key)).toEqual(SCHWARTZ_KEYS);
    expect(values).toHaveLength(10);
    expect(values.find((value) => value.key === "tradition")?.priority).toBeNull();
  });

  it("places positive priorities outside the personal mean and negative ones inside", () => {
    const mean = circumplexPoint(0, 0);
    const outward = circumplexPoint(0, 0.5);
    const inward = circumplexPoint(0, -0.5);
    expect(outward.y).toBeLessThan(mean.y);
    expect(inward.y).toBeGreaterThan(mean.y);
  });

  it("summarizes core, trade-off, and unobserved states without treating yielding as opposition", () => {
    const summary = summarizeValues(schwartzValues(dim()));
    expect(summary.core).toEqual(["self_direction"]);
    expect(summary.tradeoffs).toContain("security");
    expect(summary.unobserved).toEqual(["tradition"]);
  });

  it("centers legacy 0–100 values and never invents explicit opposition", () => {
    const legacy = legacySchwartzProfile(dim({
      profile: undefined,
      content_json: {
        achievement: { score: 78, confidence: 0.7 },
        security: { score: 76, confidence: 0.7 },
        conformity: { score: 61, confidence: 0.4 },
      },
    }));
    expect(legacy.values.achievement.priority).toBeGreaterThan(0);
    expect(legacy.values.conformity.priority).toBeLessThan(0);
    expect(legacy.values.conformity.explicit_opposition).toBe(false);
    expect(legacy.values.tradition.priority).toBeNull();
  });
});
