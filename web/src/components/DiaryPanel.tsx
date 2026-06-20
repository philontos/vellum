import { useEffect, useRef, useState } from "react";
import { getDiary, getDiaryMessages, type DiaryCard, type Message } from "../api/client";
import { groupByDay } from "../diary/group";
import { useT } from "../i18n";
import { usePrivacyBlur } from "../privacy/PrivacyProvider";
import { dayLabel } from "../util/day";
import { MessageBubble } from "./MessageBubble";

const PAGE = 20;

/**
 * The diary: the conversation's background summaries laid out as a timeline of
 * cards, grouped by day. Each card is one span's one-paragraph digest; open it to
 * load and read the full messages of that span. Scrolls down to page further back.
 */
export function DiaryPanel() {
  const { t, lang } = useT();
  const blur = usePrivacyBlur();
  const [cards, setCards] = useState<DiaryCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [atEnd, setAtEnd] = useState(false);
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Record<number, Message[]>>({});

  const loadingRef = useRef(false);
  const atEndRef = useRef(false);
  const cardsRef = useRef<DiaryCard[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    cardsRef.current = cards;
  }, [cards]);

  async function loadMore() {
    if (loadingRef.current || atEndRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    try {
      const seen = cardsRef.current;
      const before = seen.length ? seen[seen.length - 1].id : undefined;
      const page = await getDiary(before, PAGE);
      setCards((c) => [...c, ...page]);
      if (page.length < PAGE) {
        atEndRef.current = true;
        setAtEnd(true);
      }
    } catch (e) {
      console.error("diary load failed", e);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Page further back when the bottom sentinel scrolls into view.
  useEffect(() => {
    const el = bottomRef.current;
    const root = scrollRef.current;
    if (!el || !root || atEnd) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { root },
    );
    obs.observe(el);
    return () => obs.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atEnd, cards.length]);

  async function toggle(card: DiaryCard) {
    if (openId === card.id) {
      setOpenId(null);
      return;
    }
    setOpenId(card.id);
    if (!detail[card.id]) {
      try {
        const { messages } = await getDiaryMessages(card.id);
        setDetail((d) => ({ ...d, [card.id]: messages }));
      } catch (e) {
        console.error("diary detail failed", e);
      }
    }
  }

  const days = groupByDay(cards);

  return (
    <div className="v-canvas flex h-full flex-col">
      <div className="border-b border-line px-5 py-3 text-sm text-muted">{t("diary.sub")}</div>
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-[52rem] flex-col gap-5 px-5 py-8">
          {days.map((d) => (
            <div key={d.day} className="flex flex-col gap-3">
              <div className="v-timebreak" aria-hidden>
                {d.day ? dayLabel(d.cards[0].created_at, lang) : ""}
              </div>
              {d.cards.map((c) => (
                <div key={c.id} className="rounded-xl border border-line bg-surface px-4 py-3">
                  <button
                    type="button"
                    onClick={() => toggle(c)}
                    className="flex w-full items-start gap-3 text-left"
                  >
                    <span className="mt-1 h-1.5 w-1.5 flex-none rounded-full bg-gold" />
                    <span className="min-w-0 flex-1">
                      <span className={`block text-[13.5px] leading-[1.6] text-ink-soft ${blur}`}>
                        {c.content}
                      </span>
                      <span className="mt-1.5 block font-mono text-[11px] text-muted">
                        {c.created_at?.slice(11, 16)} · {t("diary.span", { start: c.start_turn, end: c.end_turn })}
                        {" · "}
                        {openId === c.id ? t("diary.collapse") : t("diary.open")}
                      </span>
                    </span>
                  </button>
                  {openId === c.id && (
                    <div className="mt-4 flex flex-col gap-5 border-t border-line/70 pt-4">
                      {(detail[c.id] ?? []).map((m) => (
                        <MessageBubble key={m.turn} m={m} latest={false} streaming={false} />
                      ))}
                      {!detail[c.id] && <div className="text-xs text-muted">{t("diary.loading")}</div>}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ))}
          {cards.length === 0 && !loading && <div className="p-8 text-muted">{t("diary.empty")}</div>}
          <div ref={bottomRef} aria-hidden className="h-px" />
          {loading && <div className="py-4 text-center text-xs text-muted">{t("diary.loading")}</div>}
          {atEnd && cards.length > 0 && (
            <div className="py-4 text-center text-xs text-muted">{t("diary.end")}</div>
          )}
        </div>
      </div>
    </div>
  );
}
