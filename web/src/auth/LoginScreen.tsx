import { useState, type FormEvent } from "react";
import { useT } from "../i18n";
import { useAuth } from "./AuthProvider";

export function LoginScreen() {
  const { login } = useAuth();
  const { t, lang, setLang } = useT();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [failed, setFailed] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!username.trim() || !password || submitting) return;
    setSubmitting(true);
    setFailed(false);
    try {
      await login(username.trim(), password);
    } catch {
      setFailed(true);
      setPassword("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="v-canvas v-safe-y flex h-full h-dvh min-h-0 items-start justify-center overflow-y-auto px-4 sm:items-center sm:px-5">
      <section className="my-auto w-full max-w-[390px] rounded-2xl border border-line bg-surface p-5 shadow-float sm:p-9">
        <div className="relative mb-1 w-max font-serif text-[31px] font-medium tracking-tight text-ink">
          Vellum
          <span className="absolute bottom-2 left-0 h-0.5 w-[29px] rounded-full bg-accent" />
        </div>
        <p className="mb-6 text-sm text-muted sm:mb-8">{t("auth.subtitle")}</p>

        <form className="space-y-4" onSubmit={submit}>
          <label className="block text-xs font-medium text-ink-soft">
            {t("auth.username")}
            <input
              autoFocus
              autoCapitalize="none"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-1.5 min-h-11 w-full rounded-lg border border-line bg-well px-3.5 py-2.5 text-base sm:text-sm text-ink outline-none transition-colors focus:border-accent"
            />
          </label>
          <label className="block text-xs font-medium text-ink-soft">
            {t("auth.password")}
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1.5 min-h-11 w-full rounded-lg border border-line bg-well px-3.5 py-2.5 text-base sm:text-sm text-ink outline-none transition-colors focus:border-accent"
            />
          </label>
          {failed && <p className="text-xs text-status-fail-fg">{t("auth.invalid")}</p>}
          <button
            type="submit"
            disabled={submitting || !username.trim() || !password}
            className="min-h-11 w-full rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-fg transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting ? t("auth.signingIn") : t("auth.signIn")}
          </button>
        </form>

        <div className="mt-7 flex items-center justify-between border-t border-line pt-4 text-xs text-muted">
          <span>{t("auth.privateFamily")}</span>
          <button
            onClick={() => setLang(lang === "en" ? "zh" : "en")}
            className="rounded-full border border-line bg-well px-2.5 py-1 text-ink-soft"
          >
            {lang === "en" ? "中" : "EN"}
          </button>
        </div>
      </section>
    </main>
  );
}
