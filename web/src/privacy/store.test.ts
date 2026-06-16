import { describe, expect, it } from "vitest";
import { createPrivacyStore, type PinRecord, type PinStorage } from "./store";

// In-memory stand-in for the localStorage-backed PinStorage, so the store logic
// can be tested in the node env (no jsdom, no real localStorage).
function fakeStorage(seed: PinRecord | null = null): PinStorage {
  let rec = seed;
  return {
    read: () => rec,
    write: (r) => {
      rec = r;
    },
    clear: () => {
      rec = null;
    },
  };
}

describe("privacy store", () => {
  it("starts hidden with no pin set", () => {
    const s = createPrivacyStore(fakeStorage());
    expect(s.getSnapshot()).toEqual({ hidden: true, hasPin: false });
  });

  it("lazily sets the pin on first reveal, then shows", async () => {
    const storage = fakeStorage();
    const s = createPrivacyStore(storage);
    const ok = await s.reveal("1234");
    expect(ok).toBe(true);
    expect(s.getSnapshot()).toEqual({ hidden: false, hasPin: true });
    expect(storage.read()).not.toBeNull(); // persisted
  });

  it("defaults to hidden on every load even after a pin exists", async () => {
    const storage = fakeStorage();
    await createPrivacyStore(storage).reveal("1234"); // set + reveal in one store
    const fresh = createPrivacyStore(storage); // simulate reload
    expect(fresh.getSnapshot()).toEqual({ hidden: true, hasPin: true });
  });

  it("reveals with the correct pin and refuses a wrong one", async () => {
    const storage = fakeStorage();
    await createPrivacyStore(storage).reveal("1234"); // establish pin
    const s = createPrivacyStore(storage);
    expect(await s.reveal("0000")).toBe(false);
    expect(s.getSnapshot().hidden).toBe(true);
    expect(await s.reveal("1234")).toBe(true);
    expect(s.getSnapshot().hidden).toBe(false);
  });

  it("hides without needing a pin", async () => {
    const storage = fakeStorage();
    const s = createPrivacyStore(storage);
    await s.reveal("1234");
    s.hide();
    expect(s.getSnapshot().hidden).toBe(true);
  });

  it("resetPin clears the pin and returns to hidden", async () => {
    const storage = fakeStorage();
    const s = createPrivacyStore(storage);
    await s.reveal("1234");
    s.resetPin();
    expect(s.getSnapshot()).toEqual({ hidden: true, hasPin: false });
    expect(storage.read()).toBeNull();
  });

  it("notifies subscribers on state change and stops after unsubscribe", async () => {
    const s = createPrivacyStore(fakeStorage());
    let calls = 0;
    const unsub = s.subscribe(() => calls++);
    await s.reveal("1234");
    expect(calls).toBeGreaterThan(0);
    const seen = calls;
    unsub();
    s.hide();
    expect(calls).toBe(seen);
  });

  it("keeps a stable snapshot reference until state changes", async () => {
    const s = createPrivacyStore(fakeStorage());
    const a = s.getSnapshot();
    expect(s.getSnapshot()).toBe(a); // same ref — safe for useSyncExternalStore
    await s.reveal("1234");
    expect(s.getSnapshot()).not.toBe(a); // new ref after change
  });
});
