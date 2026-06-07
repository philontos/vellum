"""GET /history — load the recent tail of the single eternal stream for the UI
on page load (oldest-first)."""
from fastapi import APIRouter

from app.store import memory

router = APIRouter()


@router.get("/history")
def history(limit: int = 200):
    return {"messages": memory.recent_tail(limit)}
