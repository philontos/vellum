"""GET /history — one context stream for the chat view (oldest-first). `stream`
selects the mode's conversation (daily vs counseling); without it the default
stream loads. Without `before` it loads the recent tail (page load). With
`before=<turn>` it loads the window immediately older than that turn — the chat's
scroll-up page. DELETE /history/{turn} soft-deletes a stray turn so it leaves every
model-facing read path (reversible at the db level — see memory.soft_delete)."""
from fastapi import APIRouter, Query

from app.store import memory

router = APIRouter()


@router.get("/history")
def history(
    limit: int = Query(default=200, ge=1, le=10000),
    before: int | None = Query(default=None),
    stream: str = Query(default="neutral"),
):
    # next_turn is the GLOBAL turn the server will assign next (turns are unique
    # across streams). The client seeds its optimistic counter from it so a turn
    # sent in a sparse/empty stream still gets the right global id — otherwise a
    # delete could hit another stream's turn.
    next_turn = memory.max_turn() + 1
    if before is None:
        return {"messages": memory.recent_tail(limit, stream=stream), "next_turn": next_turn}
    return {"messages": memory.messages_before(before, limit, stream=stream), "next_turn": next_turn}


@router.delete("/history/{turn}")
def delete_history(turn: int):
    """Idempotent: deleting an unknown or already-deleted turn still returns 200
    with deleted=False, so the chat's delete button never has to handle errors."""
    return {"ok": True, "deleted": memory.soft_delete(turn)}
