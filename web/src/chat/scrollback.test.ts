import { describe, expect, it } from "vitest";
import { prependEarlier } from "./scrollback";
import type { Message } from "../api/client";

const msg = (turn: number): Message => ({ turn, role: "user", content: `m${turn}` });

describe("prependEarlier", () => {
  it("prepends an older batch ahead of the existing window", () => {
    const { messages, atCap } = prependEarlier([msg(3), msg(4)], [msg(0), msg(1), msg(2)], 100);
    expect(messages.map((m) => m.turn)).toEqual([0, 1, 2, 3, 4]);
    expect(atCap).toBe(false);
  });

  it("drops messages already present (dedup by turn)", () => {
    const { messages } = prependEarlier([msg(2), msg(3)], [msg(1), msg(2)], 100);
    expect(messages.map((m) => m.turn)).toEqual([1, 2, 3]);
  });

  it("caps total at `cap`, keeping the newest of the older batch", () => {
    // existing 8,9 (2) + cap 3 => room for 1 more, take the newest older (7)
    const { messages, atCap } = prependEarlier([msg(8), msg(9)], [msg(5), msg(6), msg(7)], 3);
    expect(messages.map((m) => m.turn)).toEqual([7, 8, 9]);
    expect(atCap).toBe(true);
  });

  it("takes nothing and reports atCap when already at the cap", () => {
    const { messages, atCap } = prependEarlier([msg(8), msg(9)], [msg(6), msg(7)], 2);
    expect(messages.map((m) => m.turn)).toEqual([8, 9]);
    expect(atCap).toBe(true);
  });
});
