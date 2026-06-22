"""Hybrid-recall core (shared by A framework-retrieval and B recall tool).

Pipeline: embed(query) -> vector search (scored) -> threshold gate ->
resolve labels to sources -> hydrate turn-neighbourhoods (message hits pull the
surrounding window INCLUDING assistant turns; summary hits use the digest +
optionally its range) -> dedup overlapping windows."""
from app import config
from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore


def _format_window(rows: list[dict]) -> str:
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


async def retrieve(query: str, k: int | None = None, min_sim: float | None = None,
                   w: int | None = None) -> list[dict]:
    """Return reference snippets for `query`. Each snippet: {start, end, text}."""
    return (await retrieve_explained(query, k=k, min_sim=min_sim, w=w))["snippets"]


async def retrieve_explained(query: str, k: int | None = None,
                             min_sim: float | None = None,
                             w: int | None = None) -> dict:
    """Read-only retrieval with the scoring kept visible (for the probe panel).

    Same pipeline as retrieve(), but returns per-hit detail — including
    below-threshold near-misses (kept=False) that retrieve() silently drops —
    alongside the final merged snippets. Shape:
      {params: {k, min_sim, w},
       hits: [{sim, kept, ref_type, anchor_turn, window}],   # nearest first
       snippets: [{start, end, text}]}"""
    k = k if k is not None else config.recall_k()
    min_sim = min_sim if min_sim is not None else config.recall_min_sim()
    w = w if w is not None else config.neighborhood_w()

    hits = VectorStore().search_scored(await embed(query), k=k)
    detail: list[dict] = []
    windows: list[tuple[int, int]] = []
    for label, sim in hits:
        kept = sim >= min_sim
        ref = memory.resolve_vector_ref(label)
        rec = {"sim": sim, "kept": kept,
               "ref_type": ref["ref_type"] if ref else None,
               "anchor_turn": None, "window": None}
        if kept and ref:
            window, anchor_turn = _window_for(ref, w)
            if window is None:
                rec["kept"] = False      # anchor gone (soft-deleted) — can't recall
            else:
                rec["window"] = list(window)
                rec["anchor_turn"] = anchor_turn
                windows.append(window)
        detail.append(rec)

    snippets = [
        {"start": start, "end": end, "text": _format_window(rows)}
        for start, end in _merge_windows(windows)
        if (rows := memory.messages_in_turn_range(start, end))
    ]
    return {"params": {"k": k, "min_sim": min_sim, "w": w},
            "hits": detail, "snippets": snippets}


def _window_for(ref: dict, w: int) -> tuple[tuple[int, int] | None, int | None]:
    """Resolve a vector ref to (turn window, anchor turn). The window is None if
    the anchor is gone (soft-deleted); anchor turn is None for summary refs."""
    if ref["ref_type"] == "message":
        anchor = memory.get_message(ref["ref_id"])
        if anchor is None:
            return None, None
        t = anchor["turn"]
        return (max(0, t - w), t + w), t
    if ref["ref_type"] == "summary":
        s = memory.get_summary(ref["ref_id"])
        if s:
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
