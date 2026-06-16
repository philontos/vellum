import { useState } from "react";
import { useT } from "../i18n";
import { usePrivacy } from "../privacy/PrivacyProvider";

/**
 * Left-rail control for the privacy screen.
 * - Shown  → 🔓, click hides immediately (no PIN needed).
 * - Hidden → 🔒, click opens a small PIN popover to reveal (first time = set PIN).
 */
export function PrivacyToggle() {
  const { t } = useT();
  const { hidden, hasPin, reveal, hide, resetPin } = usePrivacy();
  const [open, setOpen] = useState(false);
  const [pin, setPin] = useState("");
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);

  function close() {
    setOpen(false);
    setPin("");
    setError(false);
  }

  async function submit() {
    const value = pin.trim();
    if (!value || busy) return;
    setBusy(true);
    const ok = await reveal(value);
    setBusy(false);
    if (ok) close();
    else {
      setError(true);
      setPin("");
    }
  }

  function onTrigger() {
    if (hidden) setOpen((v) => !v);
    else hide();
  }

  function onReset() {
    if (window.confirm(t("privacy.resetConfirm"))) {
      resetPin();
      setPin("");
      setError(false);
      // stay open — now in "set a PIN" mode
    }
  }

  return (
    <div className="relative">
      <button
        onClick={onTrigger}
        title={hidden ? t("privacy.clickToReveal") : t("privacy.clickToHide")}
        className="flex w-full items-center gap-1.5 rounded-full border border-line bg-card px-2.5 py-1 text-xs text-muted transition-colors hover:text-ink"
      >
        <span aria-hidden>{hidden ? "🔒" : "🔓"}</span>
        <span>{hidden ? t("privacy.hidden") : t("privacy.shown")}</span>
      </button>

      {open && hidden && (
        <div className="absolute bottom-full left-0 z-10 mb-2 w-56 rounded-lg border border-card-line bg-card p-3 shadow-float">
          <div className="mb-2 text-xs font-medium text-ink-soft">
            {hasPin ? t("privacy.enterTitle") : t("privacy.setTitle")}
          </div>
          <input
            type="password"
            autoFocus
            value={pin}
            placeholder={t("privacy.placeholder")}
            onChange={(e) => {
              setPin(e.target.value);
              setError(false);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
              if (e.key === "Escape") close();
            }}
            className="w-full rounded-lg border border-card-line bg-paper px-2.5 py-1.5 text-sm text-ink-soft placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-terracotta/15"
          />
          {error && <div className="mt-1.5 text-xs text-status-fail-fg">{t("privacy.wrong")}</div>}
          <div className="mt-2.5 flex items-center justify-between">
            <button
              onClick={submit}
              disabled={busy}
              className="rounded-lg border border-card-line bg-paper px-3 py-1 text-xs text-ink-soft transition-colors hover:bg-paper-raised disabled:opacity-50"
            >
              {t("privacy.confirm")}
            </button>
            {hasPin && (
              <button
                onClick={onReset}
                className="text-xs text-muted underline-offset-2 transition-colors hover:text-ink hover:underline"
              >
                {t("privacy.forgot")}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
