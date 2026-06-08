// i18n engine. `translate` is a pure function (testable without React); the
// provider holds the active language in React state so a switch re-renders the
// whole app, and persists the choice to localStorage. Default is English; no
// browser detection.
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { DICT, DEFAULT_LANG, type Key, type Lang } from "./dict";

const STORAGE_KEY = "vellum.lang";

function readSaved(): Lang {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v && v in DICT) return v as Lang;
  } catch {
    /* localStorage unavailable (private mode / SSR) — fall through */
  }
  return DEFAULT_LANG;
}

function interpolate(s: string, params?: Record<string, unknown>): string {
  if (!params) return s;
  return s.replace(/\{(\w+)\}/g, (_, k) => (params[k] != null ? String(params[k]) : `{${k}}`));
}

/** Resolve a key to a localized, interpolated string: lang → en → raw key. */
export function translate(lang: Lang, key: Key, params?: Record<string, unknown>): string {
  const table = DICT[lang] as Record<string, string>;
  const fallback = DICT[DEFAULT_LANG] as Record<string, string>;
  let s: string | undefined = table[key];
  if (s == null) {
    if (import.meta.env?.DEV && lang !== DEFAULT_LANG) {
      console.warn(`[i18n] missing key for ${lang}: ${key}`);
    }
    s = fallback[key];
  }
  if (s == null) {
    if (import.meta.env?.DEV) console.warn(`[i18n] unknown key: ${key}`);
    return interpolate(String(key), params);
  }
  return interpolate(s, params);
}

type I18nValue = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: Key, params?: Record<string, unknown>) => string;
};

const I18nCtx = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readSaved);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore persistence failure */
    }
    if (typeof document !== "undefined") document.documentElement.lang = l;
  }, []);

  const t = useCallback(
    (key: Key, params?: Record<string, unknown>) => translate(lang, key, params),
    [lang],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nCtx.Provider value={value}>{children}</I18nCtx.Provider>;
}

export function useT(): I18nValue {
  const ctx = useContext(I18nCtx);
  if (!ctx) throw new Error("useT must be used within <I18nProvider>");
  return ctx;
}
