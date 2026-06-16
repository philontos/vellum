import { describe, expect, it } from "vitest";
import { hashPin, randomSalt, verifyPin } from "./pin";

describe("pin hashing", () => {
  it("is deterministic for the same (pin, salt)", async () => {
    const salt = "abc123";
    expect(await hashPin("1234", salt)).toBe(await hashPin("1234", salt));
  });

  it("produces a different hash for a different salt", async () => {
    expect(await hashPin("1234", "saltA")).not.toBe(await hashPin("1234", "saltB"));
  });

  it("produces a different hash for a different pin", async () => {
    const salt = "abc123";
    expect(await hashPin("1234", salt)).not.toBe(await hashPin("9999", salt));
  });

  it("verifies the correct pin and rejects a wrong one", async () => {
    const salt = randomSalt();
    const hash = await hashPin("hunter2", salt);
    expect(await verifyPin("hunter2", salt, hash)).toBe(true);
    expect(await verifyPin("nope", salt, hash)).toBe(false);
  });
});

describe("randomSalt", () => {
  it("returns a 32-char hex string (16 random bytes)", () => {
    expect(randomSalt()).toMatch(/^[0-9a-f]{32}$/);
  });

  it("is different each call (practically)", () => {
    expect(randomSalt()).not.toBe(randomSalt());
  });
});
