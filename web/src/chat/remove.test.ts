import { describe, expect, it } from "vitest";
import type { Message } from "../api/client";
import { removeTurn } from "./remove";

const msg = (turn: number): Message => ({ turn, role: "user", content: `m${turn}` });

describe("removeTurn", () => {
  it("drops the message with the given turn, keeping order", () => {
    const before = [msg(0), msg(1), msg(2)];
    expect(removeTurn(before, 1).map((m) => m.turn)).toEqual([0, 2]);
  });

  it("returns the list unchanged when the turn is absent", () => {
    const before = [msg(0), msg(1)];
    expect(removeTurn(before, 9)).toEqual(before);
  });
});
