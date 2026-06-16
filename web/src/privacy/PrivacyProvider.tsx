// React binding for the privacy store. The store (store.ts) owns the logic;
// this just exposes it through context and re-renders on change.
import {
  createContext,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { createPrivacyStore, type PrivacyStore } from "./store";

type PrivacyValue = {
  hidden: boolean;
  hasPin: boolean;
  reveal: (pin: string) => Promise<boolean>;
  hide: () => void;
  resetPin: () => void;
};

const PrivacyCtx = createContext<PrivacyValue | null>(null);

export function PrivacyProvider({
  children,
  store,
}: {
  children: ReactNode;
  store?: PrivacyStore; // injectable for tests / storybook
}) {
  const s = useMemo(() => store ?? createPrivacyStore(), [store]);
  const state = useSyncExternalStore(s.subscribe, s.getSnapshot, s.getSnapshot);
  const value = useMemo<PrivacyValue>(
    () => ({
      hidden: state.hidden,
      hasPin: state.hasPin,
      reveal: s.reveal,
      hide: s.hide,
      resetPin: s.resetPin,
    }),
    [state, s],
  );
  return <PrivacyCtx.Provider value={value}>{children}</PrivacyCtx.Provider>;
}

export function usePrivacy(): PrivacyValue {
  const ctx = useContext(PrivacyCtx);
  if (!ctx) throw new Error("usePrivacy must be used within <PrivacyProvider>");
  return ctx;
}

/**
 * Tailwind classes for masking a sensitive text node while privacy mode is on.
 * Wrap the actual text (e.g. a <span>) so layout/whitespace is unaffected —
 * white-space is inherited, so an inner span still wraps like its parent.
 */
export function usePrivacyBlur(): string {
  const { hidden } = usePrivacy();
  return hidden
    ? "blur-[7px] select-none transition-[filter] duration-200"
    : "transition-[filter] duration-200";
}
