import { useState, type ReactNode } from "react";
import { useT } from "../../i18n";
import { NavItem } from "./NavItem";
import type { AuthUser } from "../../auth/client";

export type View = "chat" | "diary" | "model" | "traces" | "probe" | "prompts" | "evals";

type NavEntry = { key: View; label: string };

/**
 * Desktop keeps the manuscript rail; phones get a compact header and an
 * off-canvas menu so the conversation owns the full viewport width.
 */
export function AppShell({
  view,
  onChange,
  user,
  onLogout,
  children,
}: {
  view: View;
  onChange: (v: View) => void;
  user: AuthUser | null;
  onLogout?: () => Promise<void>;
  children: ReactNode;
}) {
  const { t, lang, setLang } = useT();
  const [mobileOpen, setMobileOpen] = useState(false);
  const nav: NavEntry[] = [
    { key: "chat", label: t("nav.chat") },
    { key: "diary", label: t("nav.diary") },
    { key: "model", label: t("nav.you") },
    { key: "traces", label: t("nav.traces") },
    { key: "probe", label: t("nav.probe") },
    ...(user?.role === "member" ? [] : [
      { key: "prompts" as const, label: t("nav.prompts") },
      { key: "evals" as const, label: t("nav.evals") },
    ]),
  ];
  const mobileNav = nav.filter(
    ({ key }) => key === "chat" || key === "diary" || key === "model",
  );
  const current = nav.find((item) => item.key === view)?.label;

  function navigate(next: View) {
    onChange(next);
    setMobileOpen(false);
  }

  const controls = () => (
    <AccountControls
      user={user}
      onLogout={onLogout}
      lang={lang}
      onLanguageChange={() => setLang(lang === "en" ? "zh" : "en")}
    />
  );

  return (
    <div className="flex h-full h-dvh w-full flex-col overflow-hidden md:flex-row">
      <header className="v-safe-top flex flex-none items-center gap-3 border-b border-line bg-[#161009] px-4 pb-3 pt-3 md:hidden">
        <button
          type="button"
          aria-label={t("nav.openMenu")}
          aria-controls="mobile-navigation"
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen(true)}
          className="flex h-10 w-10 flex-none items-center justify-center rounded-xl border border-line bg-surface text-xl text-ink-soft"
        >
          <span aria-hidden>☰</span>
        </button>
        <Wordmark compact />
        <span className="ml-auto truncate text-sm font-medium text-ink-soft">{current}</span>
      </header>

      <nav
        aria-label="Primary"
        className="hidden md:flex w-[180px] flex-none flex-col gap-0.5 border-r border-line bg-gradient-to-b from-[#161009] to-[#0e0b07] px-4 py-5"
      >
        <Wordmark />
        <Navigation entries={nav} view={view} onChange={navigate} />
        {controls()}
      </nav>

      <div
        className={`fixed inset-0 z-50 md:hidden ${mobileOpen ? "block" : "hidden"}`}
        aria-hidden={!mobileOpen}
      >
        <button
          type="button"
          aria-label={t("nav.closeMenu")}
          className="absolute inset-0 bg-black/65 backdrop-blur-[2px]"
          onClick={() => setMobileOpen(false)}
        />
        <nav
          id="mobile-navigation"
          aria-label="Primary"
          className="v-safe-y relative flex h-full h-dvh w-[min(20rem,86vw)] flex-col gap-1 border-r border-line bg-gradient-to-b from-[#161009] to-[#0e0b07] px-4 py-4 shadow-float"
        >
          <div className="mb-3 flex items-center justify-between px-2.5">
            <Wordmark compact />
            <button
              type="button"
              aria-label={t("nav.closeMenu")}
              onClick={() => setMobileOpen(false)}
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface text-lg text-muted"
            >
              <span aria-hidden>✕</span>
            </button>
          </div>
          <Navigation entries={mobileNav} view={view} onChange={navigate} />
          {controls()}
        </nav>
      </div>

      <main className="v-canvas flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">{children}</main>
    </div>
  );
}

function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`relative w-max font-serif font-medium tracking-tight text-ink ${
        compact ? "text-[23px]" : "mb-4 px-2.5 pt-0.5 text-[23px]"
      }`}
    >
      Vellum
      <span
        className={`absolute h-0.5 rounded-full bg-accent ${
          compact ? "bottom-1.5 left-0 w-[21px]" : "bottom-1.5 left-2.5 w-[21px]"
        }`}
      />
    </div>
  );
}

function Navigation({
  entries,
  view,
  onChange,
}: {
  entries: NavEntry[];
  view: View;
  onChange: (view: View) => void;
}) {
  return entries.map((item) => (
    <NavItem
      key={item.key}
      label={item.label}
      active={view === item.key}
      onClick={() => onChange(item.key)}
    />
  ));
}

function AccountControls({
  user,
  onLogout,
  lang,
  onLanguageChange,
}: {
  user: AuthUser | null;
  onLogout?: () => Promise<void>;
  lang: "en" | "zh";
  onLanguageChange: () => void;
}) {
  const { t } = useT();
  return (
    <div className="mt-auto flex flex-col gap-2 border-t border-line px-2.5 pt-3 text-xs text-muted">
      {user && (
        <div className="flex min-h-10 items-center justify-between gap-2">
          <span className="min-w-0 truncate text-ink-soft" title={user.username}>
            {user.display_name}
          </span>
          {onLogout && (
            <button
              onClick={() => void onLogout()}
              className="min-h-10 shrink-0 px-1 text-muted transition-colors hover:text-ink"
            >
              {t("auth.logout")}
            </button>
          )}
        </div>
      )}
      <div className="flex min-h-10 items-center justify-between">
        <span>{lang === "en" ? "EN" : "中文"}</span>
        <button
          onClick={onLanguageChange}
          title={lang === "en" ? "切换到中文" : "Switch to English"}
          className="min-h-10 rounded-full border border-line bg-surface px-3 text-ink-soft transition-colors hover:text-ink"
        >
          {lang === "en" ? "中" : "EN"}
        </button>
      </div>
    </div>
  );
}
