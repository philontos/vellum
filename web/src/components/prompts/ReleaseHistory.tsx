import type { PromptRelease } from "../../api/prompts";
import { useT } from "../../i18n";
import type { PromptBusy } from "./PromptEditor";

export function ReleaseHistory({
  releases,
  busy,
  onRestore,
}: {
  releases: PromptRelease[];
  busy: PromptBusy;
  onRestore: (release: PromptRelease) => void;
}) {
  const { t } = useT();

  return (
    <section className="overflow-hidden rounded-xl border border-line bg-surface shadow-card">
      <div className="border-b border-line px-4 py-3 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
        {t("prompts.history")}
      </div>
      <div>
        {releases.length === 0 && <div className="p-4 text-sm text-muted">{t("prompts.noActive")}</div>}
        {releases.map((release) => (
          <div key={release.id} className="flex flex-wrap items-center gap-2 border-b border-line/70 px-4 py-3 last:border-b-0">
            <span className="font-mono text-sm text-ink">v{release.version}</span>
            {release.is_active && (
              <span className="rounded-full bg-status-pass-bg px-2 py-0.5 text-[10px] text-status-pass-fg">
                {t("prompts.active", { version: release.version })}
              </span>
            )}
            <span className="min-w-0 flex-1 truncate text-xs text-ink-soft">
              {release.note || "—"}
            </span>
            <span className="w-full font-mono text-[10px] text-muted sm:w-auto">
              {release.published_at}
            </span>
            <button
              type="button"
              disabled={busy !== null || release.is_active}
              onClick={() => onRestore(release)}
              className="min-h-10 rounded-lg border border-line bg-well px-3 text-xs text-accent transition-colors hover:text-accent-ink disabled:cursor-not-allowed disabled:text-muted disabled:opacity-60"
            >
              {busy === "restore" ? t("prompts.restoring") : t("prompts.loadDraft")}
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
