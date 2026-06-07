"""GET /history — load the recent tail of the single eternal stream for the UI
on page load (oldest-first)."""
from fastapi import APIRouter, Query

from app.store import memory

router = APIRouter()


@router.get("/history")
def history(limit: int = Query(default=200, ge=1, le=10000)):
    return {"messages": memory.recent_tail(limit)}
