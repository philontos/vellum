"""The diary: a timeline of conversation 'cards' (the background summary spans),
newest-first and keyset-paginated by id, plus per-card detail that expands a card
into the full message span it digests. Read-only; not part of the chat hot path."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.store import memory

router = APIRouter()


@router.get("/diary")
def diary(
    limit: int = Query(default=20, ge=1, le=200),
    before: int | None = Query(default=None),
    stream: str | None = Query(default=None),
):
    # stream None merges every mode into one timeline; a value scopes the diary to
    # that mode. Each card carries its own `stream` regardless, so a merged view can
    # label or segment it later for free.
    return {"cards": memory.list_summaries(limit=limit, before_id=before, stream=stream)}


@router.get("/diary/{summary_id}")
def diary_detail(summary_id: int):
    s = memory.get_summary(summary_id)
    if s is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return {
        "summary": s,
        "messages": memory.messages_in_turn_range(s["start_turn"], s["end_turn"]),
    }
