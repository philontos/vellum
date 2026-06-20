"""GET /history — the single eternal stream for the chat view (oldest-first).
Without `before` it loads the recent tail (page load). With `before=<turn>` it
loads the window immediately older than that turn — the chat's scroll-up page."""
from fastapi import APIRouter, Query

from app.store import memory

router = APIRouter()


@router.get("/history")
def history(
    limit: int = Query(default=200, ge=1, le=10000),
    before: int | None = Query(default=None),
):
    if before is None:
        return {"messages": memory.recent_tail(limit)}
    return {"messages": memory.messages_before(before, limit)}
