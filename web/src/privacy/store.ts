// Framework-agnostic store for the local privacy screen. Holds two booleans:
//   hidden — is sensitive text currently masked? (always true on a fresh load)
//   hasPin — has a PIN been set on this browser yet?
//
// Kept free of React so the logic is unit-testable in the node env. The React
// binding lives in PrivacyProvider.tsx via useSyncExternalStore. See pin.ts for
// the honest "this is not encryption" caveat.

import { hashPin, randomSalt, verifyPin } from "./pin";

export type PinRecord = { salt: string; hash: string };

/** Persistence seam — real impl uses localStorage; tests pass an in-memory fake. */
export interface PinStorage {
  read(): PinRecord | null;
  write(rec: PinRecord): void;
  clear(): void;
}

export type PrivacyState = { hidden: boolean; hasPin: boolean };

const PIN_KEY = "vellum.privacy.pin";

/** localStorage-backed PinStorage. Per-browser, per-profile; never synced. */
export const localPinStorage: PinStorage = {
  read() {
    try {
      const raw = localStorage.getItem(PIN_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as Partial<PinRecord>;
      if (typeof parsed?.salt === "string" && typeof parsed?.hash === "string") {
        return { salt: parsed.salt, hash: parsed.hash };
      }
      return null;
    } catch {
      return null; // unavailable / corrupt — treat as no pin
    }
  },
  write(rec) {
    try {
      localStorage.setItem(PIN_KEY, JSON.stringify(rec));
    } catch {
      /* ignore persistence failure (private mode, etc.) */
    }
  },
  clear() {
    try {
      localStorage.removeItem(PIN_KEY);
    } catch {
      /* ignore */
    }
  },
};

export type PrivacyStore = {
  getSnapshot(): PrivacyState;
  subscribe(listener: () => void): () => void;
  /** Mask content. Always allowed — hiding never needs a PIN. */
  hide(): void;
  /**
   * Try to reveal. With no PIN yet, the given value becomes the PIN (lazy set)
   * and content is shown. Otherwise the value is verified. Resolves to whether
   * content is now shown. A reveal lasts only this session — reload re-hides.
   */
  reveal(pin: string): Promise<boolean>;
  /** Forget the PIN and re-hide. Used by "forgot PIN" — data is never lost. */
  resetPin(): void;
};

export function createPrivacyStore(storage: PinStorage = localPinStorage): PrivacyStore {
  let hidden = true; // default hidden: every load starts masked
  let hasPin = storage.read() !== null;
  let snapshot: PrivacyState = { hidden, hasPin };
  const listeners = new Set<() => void>();

  const commit = () => {
    snapshot = { hidden, hasPin }; // fresh ref only on change — safe for useSyncExternalStore
    for (const l of listeners) l();
  };

  return {
    getSnapshot: () => snapshot,
    subscribe(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    hide() {
      if (!hidden) {
        hidden = true;
        commit();
      }
    },
    async reveal(pin) {
      const rec = storage.read();
      if (!rec) {
        const salt = randomSalt();
        const hash = await hashPin(pin, salt);
        storage.write({ salt, hash });
        hasPin = true;
        hidden = false;
        commit();
        return true;
      }
      const ok = await verifyPin(pin, rec.salt, rec.hash);
      if (ok) {
        hidden = false;
        commit();
      }
      return ok;
    },
    resetPin() {
      storage.clear();
      hasPin = false;
      hidden = true;
      commit();
    },
  };
}
