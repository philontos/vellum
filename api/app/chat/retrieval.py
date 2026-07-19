"""Hybrid-recall core (shared by A framework-retrieval and B recall tool).

Pipeline: embed(query) -> vector search (scored) -> threshold gate ->
resolve labels to sources -> hydrate turn-neighbourhoods -> remove explicitly
excluded live-context turns -> dedup overlapping windows. Summary hits expand to
raw turns by default for the Admin probe; bounded responder paths request their
stored digest instead."""
from app import config
from app.chat import temporal
from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore


def _format_window(rows: list[dict]) -> str:
    return temporal.render_transcript(rows)


async def retrieve(query: str, stream: str = "neutral", k: int | None = None,
                   min_sim: float | None = None, w: int | None = None,
                   through_turn: int | None = None,
                   exclude_turns: set[int] | None = None,
                   summary_mode: str = "raw") -> list[dict]:
    """Return reference snippets for `query`, scoped to `stream`. Each snippet:
    {start, end, text}."""
    return (await retrieve_explained(
        query, stream=stream, k=k, min_sim=min_sim, w=w,
        through_turn=through_turn, exclude_turns=exclude_turns,
        summary_mode=summary_mode,
    ))["snippets"]


async def retrieve_explained(query: str, stream: str = "neutral", k: int | None = None,
                             min_sim: float | None = None,
                             w: int | None = None,
                             through_turn: int | None = None,
                             exclude_turns: set[int] | None = None,
                             summary_mode: str = "raw") -> dict:
    """Read-only retrieval with the scoring kept visible (for the probe panel).

    Same pipeline as retrieve(), but returns per-hit detail — including
    below-threshold near-misses (kept=False) that retrieve() silently drops —
    alongside the final merged snippets. Each kept hit also carries the turns it
    would hydrate (`rows`: {turn, role, content}) so the probe can show each hit's
    own window before the merge; summary hits additionally carry their `digest`.
    `summary_mode=raw` retains the probe's raw hydration, while `digest` keeps
    responder recall bounded and avoids re-expanding compacted history. Shape:
      {params: {k, min_sim, w},
       hits: [{sim, kept, ref_type, anchor_turn, window, digest, rows}],  # nearest first
       snippets: [{start, end, text}]}                                    # merged, deduped"""
    if summary_mode not in {"raw", "digest"}:
        raise ValueError(f"Unknown summary mode {summary_mode!r}")
    excluded = set(exclude_turns or ())
    k = k if k is not None else config.recall_k()
    min_sim = min_sim if min_sim is not None else config.recall_min_sim()
    w = w if w is not None else config.neighborhood_w()

    hits = VectorStore().search_scored(await embed(query), k=k)
    detail: list[dict] = []
    windows: list[tuple[int, int]] = []
    digest_snippets: list[dict] = []
    seen_digests: set[tuple[int, int, str]] = set()
    for label, sim in hits:
        kept = sim >= min_sim
        ref = memory.resolve_vector_ref(label)
        rec = {"sim": sim, "kept": kept,
               "ref_type": ref["ref_type"] if ref else None,
               "anchor_turn": None, "window": None, "digest": None, "rows": []}
        if kept and ref:
            window, anchor_turn = _window_for(
                ref, w, stream, through_turn=through_turn,
                exclude_turns=excluded,
            )
            rec["anchor_turn"] = anchor_turn
            if window is None:
                rec["kept"] = False      # anchor gone, or in another stream — can't recall
            else:
                rec["window"] = list(window)
                rec["rows"] = [
                    {"turn": r["turn"], "role": r["role"], "content": r["content"]}
                    for r in memory.messages_in_turn_range(*window, stream=stream)
                    if r["turn"] not in excluded
                ]
                if ref["ref_type"] == "summary":
                    s = memory.get_summary(ref["ref_id"])
                    rec["digest"] = s["content"] if s else None
                    if summary_mode == "digest":
                        overlaps_excluded = any(
                            window[0] <= turn <= window[1] for turn in excluded
                        )
                        digest = (rec["digest"] or "").strip()
                        if overlaps_excluded or not digest:
                            rec["kept"] = False
                        else:
                            key = (window[0], window[1], digest)
                            if key not in seen_digests:
                                digest_snippets.append({
                                    "start": window[0], "end": window[1],
                                    "text": f"summary: {digest}",
                                })
                                seen_digests.add(key)
                        detail.append(rec)
                        continue
                if rec["rows"]:
                    windows.append(window)
                else:
                    rec["kept"] = False
        detail.append(rec)

    snippets = digest_snippets + [
        {"start": start, "end": end, "text": _format_window(rows)}
        for start, end in _merge_windows(windows)
        if (rows := [
            row for row in memory.messages_in_turn_range(
                start, end, stream=stream,
            ) if row["turn"] not in excluded
        ])
    ]
    return {"params": {"k": k, "min_sim": min_sim, "w": w},
            "hits": detail, "snippets": snippets}


def _window_for(
    ref: dict, w: int, stream: str, through_turn: int | None = None,
    exclude_turns: set[int] | None = None,
) -> tuple[tuple[int, int] | None, int | None]:
    """Resolve a vector ref to (turn window, anchor turn), scoped to `stream`. The
    window is None if the anchor is gone (soft-deleted) OR belongs to another stream
    — so a hit from a different mode's transcript never bleeds into this one. Anchor
    turn is None for summary refs."""
    if ref["ref_type"] == "message":
        anchor = memory.get_message(ref["ref_id"])
        if anchor is None or anchor["stream"] != stream:
            return None, None
        t = anchor["turn"]
        if t in (exclude_turns or set()):
            return None, t
        if through_turn is not None and t > through_turn:
            return None, None
        end = min(t + w, through_turn) if through_turn is not None else t + w
        return (max(0, t - w), end), t
    if ref["ref_type"] == "summary":
        s = memory.get_summary(ref["ref_id"])
        if s and s["stream"] == stream:
            # A summary embedding represents its whole span. If any part of that
            # span is in the replay's future, even using it only to choose an old
            # raw window would leak information through retrieval ranking.
            if through_turn is not None and s["end_turn"] > through_turn:
                return None, None
            return (s["start_turn"], s["end_turn"]), None
    return None, None


def _merge_windows(windows: list[tuple[int, int]]) -> list[list[int]]:
    """Sort and merge overlapping/adjacent [start, end] turn windows."""
    windows = sorted(windows)
    merged: list[list[int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged
