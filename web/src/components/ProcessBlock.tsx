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
  const thinking = live && !hasContent;

  return (
    <div className="mb-2.5 text-[12.5px]">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-left text-muted transition-colors hover:text-ink-soft"
      >
        {thinking ? (
          <span className="v-think-dot" aria-hidden />
        ) : (
          <span className="text-[9px] opacity-60">{open ? "▾" : "▸"}</span>
        )}
        <span className="font-serif italic">{header}</span>
      </button>
      {open && (
        <div className="v-gloss mt-1.5 flex flex-col gap-1">
          {items.map((it, i) => (
            <div key={i} className="flex items-baseline gap-1.5 text-ink-soft/70">
              <span aria-hidden className="text-[10px] opacity-70">
                {icon(it.status)}
              </span>
              <span className="font-mono text-[11px] opacity-80">{it.name}</span>
              {it.query ? <span className="italic opacity-70">“{it.query}”</span> : null}
            </div>
          ))}
          {hasReasoning && (
            <div className="whitespace-pre-wrap font-serif italic leading-relaxed text-muted">
              {reasoning}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
