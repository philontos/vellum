import { useEffect, useState } from "react";
import { getModel, type Fact, type ModelView } from "../api/client";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";

/**
 * The conversation's right-hand companion on wide screens: a quiet running read
 * of what Vellum is piecing together about you (its most recent facts), so the
 * page's width carries the product's other half instead of empty margin. The
 * parent hides it below xl, where the conversation reverts to a single column.
 */
export function ContextRail({
  turns,
  data,
  className = "",
}: {
  turns: number;
  data?: ModelView | null; // injected in preview/tests; otherwise fetched live
  className?: string;
}) {
  const { t } = useT();
  const blur = usePrivacyBlur();
  const injected = data !== undefined;
  const [model, setModel] = useState<ModelView | null>(injected ? data ?? null : null);

  useEffect(() => {
    if (injected) return;
    let alive = true;
    getModel()
      .then((m) => alive && setModel(m))
      .catch(() => {
        /* the rail is ambient — stay quiet if the model isn't ready */
      });
    return () => {
      alive = false;
    };
  }, [injected]);

  const facts: Fact[] = (model?.facts ?? [])
    .filter((f) => f.status === "active")
    .sort((a, b) => (b.source_turn ?? 0) - (a.source_turn ?? 0))
    .slice(0, 8);

  return (
    <aside className={`flex-none flex-col ${className}`}>
      <div className="flex h-full flex-col gap-6 px-6 py-10">
        <header>
          <div className="v-eyebrow v-eyebrow--vellum">{t("rail.title")}</div>
          <p className="font-serif text-[15px] leading-snug text-ink-soft">{t("rail.sub")}</p>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="mb-3 text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
            {t("rail.factsTitle")}
          </div>
          {facts.length === 0 ? (
            <p className="text-[13px] leading-relaxed text-muted">{t("rail.empty")}</p>
          ) : (
            <ul className="space-y-3">
              {facts.map((f) => (
                <li key={f.id} className="relative pl-4 text-[13px] leading-[1.55] text-ink-soft">
                  <span
                    className="absolute left-0 top-[0.5em] h-1.5 w-1.5 rounded-full border border-gold/70"
                    aria-hidden
                  />
                  <span className={blur}>{f.text}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <footer className="border-t border-line pt-3 text-[10px] uppercase tracking-[0.16em] text-muted">
          {t("rail.session", { n: String(turns) })}
        </footer>
      </div>
    </aside>
  );
}
