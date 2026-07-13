import { afterEach, describe, expect, it, vi } from "vitest";
import { hashPin, randomSalt, verifyPin } from "./pin";

afterEach(() => vi.unstubAllGlobals());

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

  it("keeps working when SubtleCrypto is unavailable on an HTTP origin", async () => {
    const cases = [
      { pin: "1234", salt: "abc123" },
      { pin: "密碼", salt: "盐" },
      { pin: "x".repeat(100), salt: "s".repeat(80) },
    ];
    const expected = await Promise.all(cases.map(({ pin, salt }) => hashPin(pin, salt)));
    vi.stubGlobal("crypto", {
      getRandomValues: crypto.getRandomValues.bind(crypto),
    });

    await Promise.all(
      cases.map(async ({ pin, salt }, index) => {
        expect(await hashPin(pin, salt)).toBe(expected[index]);
      }),
    );
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
