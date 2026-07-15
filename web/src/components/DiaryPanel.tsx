import { useEffect, useRef, useState } from "react";

import { getDiary, getDiaryMessages, type DiaryCard } from "../api/client";
import { userStorageKey } from "../auth/storage";
import { groupByDay } from "../diary/group";
import { useT } from "../i18n";
import { DiaryEntry, type DiaryEntryState } from "./diary/DiaryEntry";
import { DiaryPager } from "./diary/DiaryPager";
import { DiaryTimeline } from "./diary/DiaryTimeline";

const PAGE = 20;

/**
 * The diary keeps its timeline and entry reader as two sibling pages. Opening an
 * entry slides the reader in without unmounting the timeline, so long transcripts
 * get their own scroll surface and returning preserves the reader's list position.
 */
export function DiaryPanel({ userId }: { userId?: string }) {
  const { lang } = useT();
  const personaKey = userStorageKey(userId, "persona");
  const [cards, setCards] = useState<DiaryCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [atEnd, setAtEnd] = useState(false);
  const [selected, setSelected] = useState<DiaryCard | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [details, setDetails] = useState<Record<number, DiaryEntryState>>({});
  const [stream, setStream] = useState<string>(
    () => localStorage.getItem(personaKey) || "neutral",
  );

  const loadingRef = useRef(false);
  const detailLoadingRef = useRef(new Set<number>());
  const returnFocusIdRef = useRef<number | null>(null);
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
      const { messages } = await getDiaryMessages(cardId);
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
    setSelected(card);
    setDetailOpen(true);
    const cached = details[card.id];
    if (!cached || cached.status === "error") void loadDetail(card.id);
  }

  function closeDetail() {
    setDetailOpen(false);
  }

  useEffect(() => {
    streamRef.current = stream;
    cardsRef.current = [];
    loadingRef.current = false;
    atEndRef.current = false;
    setCards([]);
    setAtEnd(false);
    setDetailOpen(false);
    void loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream]);

  useEffect(() => {
    const sentinel = bottomRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root || atEnd || detailOpen) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) void loadMore();
      },
      { root },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atEnd, cards.length, detailOpen]);

  useEffect(() => {
    if (!detailOpen) return;
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeDetail();
      }
    }
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [detailOpen]);

  useEffect(() => {
    if (selected) detailScrollRef.current?.scrollTo({ top: 0 });
  }, [selected]);

  useEffect(() => {
    if (detailOpen || returnFocusIdRef.current === null) return;
    const cardId = returnFocusIdRef.current;
    const frame = requestAnimationFrame(() => {
      scrollRef.current
        ?.querySelector<HTMLButtonElement>(`[data-diary-card="${cardId}"]`)
        ?.focus();
    });
    return () => cancelAnimationFrame(frame);
  }, [detailOpen]);

  const days = groupByDay(cards);
  const detailState = selected ? details[selected.id] : undefined;

  return (
    <div className="v-canvas flex h-full min-h-0 flex-col overflow-hidden">
      <DiaryPager
        detailOpen={detailOpen}
        timeline={(
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
        )}
        detail={(
          <DiaryEntry
            card={selected}
            state={detailState}
            active={detailOpen}
            lang={lang}
            scrollRef={detailScrollRef}
            onBack={closeDetail}
            onRetry={() => {
              if (selected) void loadDetail(selected.id);
            }}
          />
        )}
      />
    </div>
  );
}
