import { describe, expect, it } from "vitest";
import { DICT } from "./dict";
import { translate } from "./index";

describe("i18n dict", () => {
  it("zh mirrors en key-for-key (lockstep — nothing ships half-translated)", () => {
    expect(Object.keys(DICT.zh).sort()).toEqual(Object.keys(DICT.en).sort());
  });

  it("has no empty strings", () => {
    for (const lang of ["en", "zh"] as const) {
      for (const [k, v] of Object.entries(DICT[lang])) {
        expect(v, `${lang}.${k} is empty`).not.toBe("");
      }
    }
  });
});

describe("translate", () => {
  it("returns the string for the active language", () => {
    expect(translate("en", "nav.chat")).toBe("Chat");
    expect(translate("zh", "nav.chat")).toBe("聊天");
  });

  it("interpolates {name} params", () => {
    expect(translate("en", "traces.count", { n: 3 })).toBe("3 entries");
    expect(translate("zh", "traces.count", { n: 3 })).toBe("3 条");
  });

  it("leaves placeholders intact when no param is given", () => {
    expect(translate("en", "traces.count")).toBe("{n} entries");
  });

  it("returns the raw key for an unknown key", () => {
    // cast past the Key type to exercise the final fallback branch
    expect(translate("en", "does.not.exist" as never)).toBe("does.not.exist");
  });
});
