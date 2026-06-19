import type { ReactNode } from "react";
import { useT } from "../../i18n";
import { NavItem } from "./NavItem";
import { PrivacyToggle } from "../PrivacyToggle";

export type View = "chat" | "model" | "traces" | "evals";

/** Left navigation rail + main canvas. Owns nav + language toggle; panels fill the canvas. */
export function AppShell({
  view,
  onChange,
  children,
}: {
  view: View;
  onChange: (v: View) => void;
  children: ReactNode;
}) {
  const { t, lang, setLang } = useT();
  const nav: { key: View; label: string }[] = [
    { key: "chat", label: t("nav.chat") },
    { key: "model", label: t("nav.you") },
    { key: "traces", label: t("nav.traces") },
    { key: "evals", label: t("nav.evals") },
  ];

  return (
    <div className="flex h-full w-full">
      <nav className="flex w-[160px] flex-none flex-col gap-0.5 border-r border-line bg-gradient-to-b from-[#161009] to-[#0e0b07] px-4 py-5 sm:w-[180px]">
        <div className="relative mb-4 w-max px-2.5 pt-0.5 font-serif text-[23px] font-medium tracking-tight text-ink">
          Vellum
          {/* a nib stroke under the wordmark */}
          <span className="absolute bottom-1.5 left-2.5 h-0.5 w-[21px] rounded-full bg-accent" />
        </div>
        {nav.map((n) => (
          <NavItem key={n.key} label={n.label} active={view === n.key} onClick={() => onChange(n.key)} />
        ))}
        <div className="mt-auto flex flex-col gap-2 border-t border-line px-2.5 pt-3 text-xs text-muted">
          <PrivacyToggle />
          <div className="flex items-center justify-between">
            <span>{lang === "en" ? "EN" : "中文"}</span>
            <button
              onClick={() => setLang(lang === "en" ? "zh" : "en")}
              title={lang === "en" ? "切换到中文" : "Switch to English"}
              className="rounded-full border border-line bg-surface px-2.5 py-1 text-ink-soft transition-colors hover:text-ink"
            >
              {lang === "en" ? "中" : "EN"}
            </button>
          </div>
        </div>
      </nav>
      <main className="v-canvas flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
