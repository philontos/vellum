import { useEffect, useState } from "react";
import type { ActivityItem } from "../api/activity";
import { useT } from "../i18n";

/**
 * The live "thinking & searching" rail above an assistant reply: streams the
 * model's reasoning and its tool calls (e.g. web_search), then auto-collapses
 * to a one-line summary once the final answer begins. Live-only — on reload the
 * detail lives in the Traces panel, not here.
 */
export function ProcessBlock({
  reasoning,
  activity,
  live,
  hasContent,
}: {
  reasoning?: string;
  activity?: ActivityItem[];
  live: boolean;
  hasContent: boolean;
}) {
  const { t } = useT();
  const [open, setOpen] = useState(true);
  // Collapse as soon as the answer starts arriving; the user can reopen.
  useEffect(() => {
    if (hasContent) setOpen(false);
  }, [hasContent]);

  const items = activity ?? [];
  const hasReasoning = !!reasoning?.trim();
  if (!hasReasoning && items.length === 0) return null;

  const header =
    live && !hasContent
      ? t("chat.processLive")
      : items.length
        ? `${t("chat.process")} · ${t("chat.searchN", { n: items.length })}`
        : t("chat.process");

  const icon = (s: ActivityItem["status"]) => (s === "running" ? "🔍" : s === "error" ? "✗" : "✓");

  return (
    <div className="mb-2 rounded-md border border-gold/15 bg-accent/15 text-[12px] text-ink-soft">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-1.5 px-3 py-1.5 text-left opacity-75 hover:opacity-100"
      >
        <span className="text-[10px]">{open ? "▾" : "▸"}</span>
        <span>{header}</span>
      </button>
      {open && (
        <div className="flex flex-col gap-1 px-3 pb-2.5">
          {items.map((it, i) => (
            <div key={i} className="flex items-baseline gap-1.5">
              <span aria-hidden>{icon(it.status)}</span>
              <span className="font-mono opacity-80">{it.name}</span>
              {it.query ? <span className="italic opacity-70">“{it.query}”</span> : null}
            </div>
          ))}
          {hasReasoning && (
            <div className="mt-1 whitespace-pre-wrap leading-relaxed opacity-65">{reasoning}</div>
          )}
        </div>
      )}
    </div>
  );
}
