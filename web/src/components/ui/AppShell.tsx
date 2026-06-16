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
    <div className="mx-auto flex h-full max-w-[1120px] border-line sm:border-x">
      <nav className="flex w-[172px] flex-none flex-col gap-0.5 border-r border-line bg-gradient-to-b from-paper to-paper-raised px-4 py-5">
        <div className="px-2.5 pb-5 pt-0.5 font-serif text-[23px] font-medium tracking-tight text-ink">
          Vellum
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
              className="rounded-full border border-line bg-card px-2.5 py-1 text-muted transition-colors hover:text-ink"
            >
              {lang === "en" ? "中" : "EN"}
            </button>
          </div>
        </div>
      </nav>
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
