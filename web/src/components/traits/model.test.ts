import { describe, it, expect } from "vitest";
import type { TraitDim } from "../../api/client";
import { traitRows, leaning, sparkline } from "./model";

function dim(p: Partial<TraitDim>): TraitDim {
  return { dimension: "x", content_json: {}, sample_count: 0, updated_at: "", history: [], meta: null, ...p };
}

describe("traitRows", () => {
  it("follows meta order and carries poles for bipolar sub-dimensions", () => {
    const rows = traitRows(dim({
      content_json: { E_I: { score: 64 }, S_N: { score: 38 } },
      meta: { name: "MBTI", label: "MBTI", sort_by_score: false, sub_dimensions: [
        { key: "E_I", name: "E–I", poles: ["I", "E"] },
        { key: "S_N", name: "S–N", poles: ["S", "N"] },
      ] },
    }));
    expect(rows.map((r) => r.key)).toEqual(["E_I", "S_N"]);
    expect(rows[0].poles).toEqual(["I", "E"]);
    expect(rows[0].score).toBe(64);
  });

  it("sorts by score descending when meta.sort_by_score", () => {
    const rows = traitRows(dim({
      content_json: { a: { score: 30 }, b: { score: 80 }, c: { score: 55 } },
      meta: { name: "V", label: "V", sort_by_score: true, sub_dimensions: [
        { key: "a", name: "A" }, { key: "b", name: "B" }, { key: "c", name: "C" },
      ] },
    }));
    expect(rows.map((r) => r.key)).toEqual(["b", "c", "a"]);
  });

  it("derives the per-sub-dimension history series and a since-first delta", () => {
    const rows = traitRows(dim({
      content_json: { O: { score: 72 } },
      meta: { name: "O", label: "O", sort_by_score: false, sub_dimensions: [{ key: "O", name: "Openness" }] },
      history: [
        { taken_at: "1", content_json: { O: { score: 66 } } },
        { taken_at: "2", content_json: { O: { score: 70 } } },
        { taken_at: "3", content_json: { O: { score: 72 } } },
      ],
    }));
    expect(rows[0].history).toEqual([66, 70, 72]);
    expect(rows[0].delta).toBe(6);
  });

  it("leaves delta null with fewer than two history points", () => {
    const rows = traitRows(dim({
      content_json: { O: { score: 72 } },
      meta: { name: "O", label: "O", sort_by_score: false, sub_dimensions: [{ key: "O", name: "Openness" }] },
      history: [{ taken_at: "1", content_json: { O: { score: 72 } } }],
    }));
    expect(rows[0].delta).toBeNull();
  });

  it("skips sub-dimensions that have no numeric score yet", () => {
    const rows = traitRows(dim({
      content_json: { O: { score: 72 }, C: {} },
      meta: { name: "B", label: "B", sort_by_score: false, sub_dimensions: [
        { key: "O", name: "Openness" }, { key: "C", name: "Conscientiousness" },
      ] },
    }));
    expect(rows.map((r) => r.key)).toEqual(["O"]);
  });

  it("falls back to content_json keys (unipolar) when meta is absent", () => {
    const rows = traitRows(dim({ content_json: { foo: { score: 50 } }, meta: null }));
    expect(rows[0].key).toBe("foo");
    expect(rows[0].label).toBe("foo");
    expect(rows[0].poles).toBeUndefined();
  });
});

describe("leaning", () => {
  it("points to the high pole above center, the low pole below, mid at center", () => {
    expect(leaning(64, ["I", "E"])).toEqual({ pole: "E", side: "high" });
    expect(leaning(38, ["S", "N"])).toEqual({ pole: "S", side: "low" });
    expect(leaning(50, ["T", "F"]).side).toBe("mid");
  });
});

describe("sparkline", () => {
  it("maps a series to autoscaled polyline points (higher value = lower y)", () => {
    expect(sparkline([0, 50, 100], 100, 20)).toBe("0,18 50,10 100,2");
  });
  it("draws a flat midline for a constant series", () => {
    expect(sparkline([42, 42], 100, 20)).toBe("0,10 100,10");
  });
  it("draws a flat midline for a single point and empty for none", () => {
    expect(sparkline([42], 100, 20)).toBe("0,10 100,10");
    expect(sparkline([], 100, 20)).toBe("");
  });
});
