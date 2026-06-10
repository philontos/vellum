import type { Message } from "../api/client";
import { useT } from "../i18n";

export function MessageBubble({ m }: { m: Message }) {
  const { t } = useT();
  const mine = m.role === "user";
  return (
    <div className={`flex flex-col ${mine ? "items-end" : "items-start"}`}>
      <div
        className={`mb-1.5 text-[10px] font-medium uppercase tracking-[0.14em] ${
          mine ? "text-terracotta-ink" : "text-muted"
        }`}
      >
        {mine ? t("chat.you") : t("chat.vellum")}
      </div>
      {mine ? (
        // Your words — a solid ink bubble, paper-cream text.
        <div className="max-w-[78%] whitespace-pre-wrap rounded-bubble rounded-br-[5px] bg-ink px-4 py-2.5 text-sm leading-relaxed text-paper">
          {m.content || "…"}
        </div>
      ) : (
        // Vellum's reply — the serif "voice", no bubble.
        <div className="max-w-[90%] whitespace-pre-wrap font-serif text-[16.5px] leading-[1.66] text-ink-soft">
          {m.content || "…"}
        </div>
      )}
    </div>
  );
}
