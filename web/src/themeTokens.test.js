import { describe, expect, it } from "vitest";
import defaultTheme from "tailwindcss/defaultTheme.js";

import config from "../tailwind.config.js";

describe("theme tokens", () => {
  it("does not reuse font-size names for colors", () => {
    const colors = config.theme?.extend?.colors ?? {};
    const collisions = Object.keys(colors).filter(
      (name) => Object.prototype.hasOwnProperty.call(defaultTheme.fontSize, name),
    );

    expect(collisions).toEqual([]);
  });
});
