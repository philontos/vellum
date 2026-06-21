"""GET /history — the single eternal stream for the chat view (oldest-first).
Without `before` it loads the recent tail (page load). With `before=<turn>` it
loads the window immediately older than that turn — the chat's scroll-up page.
DELETE /history/{turn} soft-deletes a stray turn so it leaves every model-facing
read path (reversible at the db level — see memory.soft_delete)."""
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


@router.delete("/history/{turn}")
def delete_history(turn: int):
    """Idempotent: deleting an unknown or already-deleted turn still returns 200
    with deleted=False, so the chat's delete button never has to handle errors."""
    return {"ok": True, "deleted": memory.soft_delete(turn)}
