import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider, useAuth } from "./auth/AuthProvider";
import { LoginScreen } from "./auth/LoginScreen";
import { ConfirmProvider } from "./confirm/ConfirmProvider";
import { I18nProvider, useT } from "./i18n";
// Self-hosted fonts (offline-safe) — Newsreader (serif voice) + Inter (UI/text)
import "@fontsource/newsreader/400.css";
import "@fontsource/newsreader/500.css";
import "@fontsource/newsreader/600.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "./index.css";

function Root() {
  const auth = useAuth();
  const { t } = useT();
  if (auth.loading) {
    return <div className="v-canvas flex h-full items-center justify-center text-sm text-muted">Vellum…</div>;
  }
  if (auth.error) {
    return (
      <div className="v-canvas flex h-full flex-col items-center justify-center gap-3 text-sm text-muted">
        <span>{t("auth.unavailable")}</span>
        <button className="rounded-lg border border-line px-3 py-1.5 text-ink-soft" onClick={() => void auth.refresh()}>
          {t("auth.retry")}
        </button>
      </div>
    );
  }
  if (auth.enabled && !auth.user) return <LoginScreen />;
  return <App user={auth.user} onLogout={auth.enabled ? auth.logout : undefined} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <ConfirmProvider>
        <AuthProvider>
          <Root />
        </AuthProvider>
      </ConfirmProvider>
    </I18nProvider>
  </React.StrictMode>,
);
