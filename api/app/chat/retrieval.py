"""Hybrid-recall core (shared by A framework-retrieval and B recall tool).

Pipeline: embed(query) -> vector search (scored) -> threshold gate ->
resolve labels to sources -> hydrate turn-neighbourhoods (message hits pull the
surrounding window INCLUDING assistant turns; summary hits use the digest +
optionally its range) -> dedup overlapping windows."""
import asyncio

from app import config
from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore


def _embed_sync(text: str) -> list[float]:
    """Sync wrapper around the async embed() so retrieval is callable from sync
    assembly code. (Tests monkeypatch this.)"""
    return asyncio.run(embed(text))


def _format_window(rows: list[dict]) -> str:
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


def retrieve(query: str, k: int | None = None, min_sim: float | None = None,
             w: int | None = None) -> list[dict]:
    """Return reference snippets for `query`. Each snippet: {start, end, text}."""
    k = k if k is not None else config.recall_k()
    min_sim = min_sim if min_sim is not None else config.recall_min_sim()
    w = w if w is not None else config.neighborhood_w()

    hits = VectorStore().search_scored(_embed_sync(query), k=k)
    windows: list[tuple[int, int]] = []
    for label, sim in hits:
        if sim < min_sim:
            continue
        ref = memory.resolve_vector_ref(label)
        if not ref:
            continue
        if ref["ref_type"] == "message":
            anchor = memory.get_message(ref["ref_id"])
            if anchor is None:
                continue
            t = anchor["turn"]
            windows.append((max(0, t - w), t + w))
        elif ref["ref_type"] == "summary":
            s = memory.get_summary(ref["ref_id"])
            if s:
                windows.append((s["start_turn"], s["end_turn"]))

    # dedup / merge overlapping windows
    windows.sort()
    merged: list[list[int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    snippets = []
    for start, end in merged:
        rows = memory.messages_in_turn_range(start, end)
        if rows:
            snippets.append({"start": start, "end": end, "text": _format_window(rows)})
    return snippets
