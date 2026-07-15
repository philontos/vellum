import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { getDiary, getDiaryMessages, type DiaryCard } from "../api/client";
import { userStorageKey } from "../auth/storage";
import { groupByDay } from "../diary/group";
import { useT } from "../i18n";
import { DiaryEntry, type DiaryEntryState } from "./diary/DiaryEntry";
import { DiaryTimeline } from "./diary/DiaryTimeline";

const PAGE = 20;

/**
 * The timeline and entry reader are separate browser-history pages. The controller
 * keeps fetched cards and scroll position alive while the route swaps components.
 */
export function DiaryPanel({
  userId,
  entryId,
  onOpenEntry,
  onCloseEntry,
}: {
  userId?: string;
  entryId: number | null;
  onOpenEntry: (entryId: number) => void;
  onCloseEntry: () => void;
}) {
  const { lang } = useT();
  const personaKey = userStorageKey(userId, "persona");
  const [cards, setCards] = useState<DiaryCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [atEnd, setAtEnd] = useState(false);
  const [details, setDetails] = useState<Record<number, DiaryEntryState>>({});
  const [detailCards, setDetailCards] = useState<Record<number, DiaryCard>>({});
  const [stream, setStream] = useState<string>(
    () => localStorage.getItem(personaKey) || "neutral",
  );

  const loadingRef = useRef(false);
  const detailLoadingRef = useRef(new Set<number>());
  const returnFocusIdRef = useRef<number | null>(null);
  const timelineScrollTopRef = useRef(0);
  const atEndRef = useRef(false);
  const cardsRef = useRef<DiaryCard[]>([]);
  const streamRef = useRef(stream);
  const scrollRef = useRef<HTMLDivElement>(null);
  const detailScrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    cardsRef.current = cards;
  }, [cards]);

  async function loadMore() {
    if (loadingRef.current || atEndRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    const requestedStream = streamRef.current;
    try {
      const seen = cardsRef.current;
      const before = seen.length ? seen[seen.length - 1].id : undefined;
      const page = await getDiary(before, PAGE, requestedStream);
      if (streamRef.current !== requestedStream) return;
      setCards((current) => (before === undefined ? page : [...current, ...page]));
      if (page.length < PAGE) {
        atEndRef.current = true;
        setAtEnd(true);
      }
    } catch (error) {
      console.error("diary load failed", error);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }

  async function loadDetail(cardId: number) {
    if (detailLoadingRef.current.has(cardId)) return;
    detailLoadingRef.current.add(cardId);
    setDetails((current) => ({
      ...current,
      [cardId]: {
        status: "loading",
        messages: current[cardId]?.messages ?? [],
      },
    }));
    try {
      const { summary, messages } = await getDiaryMessages(cardId);
      setDetailCards((current) => ({ ...current, [cardId]: summary }));
      setDetails((current) => ({
        ...current,
        [cardId]: { status: "ready", messages },
      }));
    } catch (error) {
      console.error("diary detail failed", error);
      setDetails((current) => ({
        ...current,
        [cardId]: {
          status: "error",
          messages: current[cardId]?.messages ?? [],
        },
      }));
    } finally {
      detailLoadingRef.current.delete(cardId);
    }
  }

  function openDetail(card: DiaryCard) {
    returnFocusIdRef.current = card.id;
    timelineScrollTopRef.current = scrollRef.current?.scrollTop ?? 0;
    setDetailCards((current) => ({ ...current, [card.id]: card }));
    onOpenEntry(card.id);
    const cached = details[card.id];
    if (!cached || cached.status === "error") void loadDetail(card.id);
  }

  useEffect(() => {
    streamRef.current = stream;
    cardsRef.current = [];
    loadingRef.current = false;
    atEndRef.current = false;
    setCards([]);
    setAtEnd(false);
    timelineScrollTopRef.current = 0;
    void loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream]);

  useEffect(() => {
    const sentinel = bottomRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root || atEnd || entryId !== null) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) void loadMore();
      },
      { root },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atEnd, cards.length, entryId]);

  useEffect(() => {
    if (entryId === null) return;
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseEntry();
      }
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [entryId, onCloseEntry]);

  useEffect(() => {
    if (entryId !== null) detailScrollRef.current?.scrollTo({ top: 0 });
  }, [entryId]);

  useEffect(() => {
    if (entryId !== null || returnFocusIdRef.current === null) return;
    const cardId = returnFocusIdRef.current;
    const frame = requestAnimationFrame(() => {
      scrollRef.current
        ?.querySelector<HTMLAnchorElement>(`[data-diary-card="${cardId}"]`)
        ?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [entryId]);

  useLayoutEffect(() => {
    if (entryId === null && scrollRef.current) {
      scrollRef.current.scrollTop = timelineScrollTopRef.current;
    }
  }, [entryId]);

  useEffect(() => {
    if (entryId === null) return;
    const cached = details[entryId];
    if (!cached || cached.status === "error") void loadDetail(entryId);
    // Loading is keyed by the route id; cache updates must not restart the request.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entryId]);

  const days = groupByDay(cards);
  if (entryId !== null) {
    const detailCard = detailCards[entryId] ?? cards.find((card) => card.id === entryId) ?? null;
    return (
      <div className="v-canvas flex h-full min-h-0 flex-col overflow-hidden">
        <DiaryEntry
          card={detailCard}
          state={details[entryId]}
          lang={lang}
          scrollRef={detailScrollRef}
          onBack={onCloseEntry}
          onRetry={() => void loadDetail(entryId)}
        />
      </div>
    );
  }

  return (
    <div className="v-canvas flex h-full min-h-0 flex-col overflow-hidden">
      <DiaryTimeline
        days={days}
        cardCount={cards.length}
        stream={stream}
        lang={lang}
        loading={loading}
        atEnd={atEnd}
        scrollRef={scrollRef}
        bottomRef={bottomRef}
        onStreamChange={setStream}
        onOpen={openDetail}
      />
    </div>
  );
}
