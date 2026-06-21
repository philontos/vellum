"""Memory layer DAO: the global message stream, conversation summaries,
HNSW label->source mapping, and per-concern modeling cursors."""
from app.store.db import get_conn


def append_message(role: str, content: str) -> dict:
    """Append to the single eternal stream; assign the next global turn."""
    with get_conn() as conn:
        turn = conn.execute(
            "SELECT COALESCE(MAX(turn), -1) + 1 AS t FROM messages"
        ).fetchone()["t"]
        cur = conn.execute(
            "INSERT INTO messages(turn, role, content) VALUES (?, ?, ?)",
            (turn, role, content),
        )
        return {"id": cur.lastrowid, "turn": turn}


def recent_tail(limit: int) -> list[dict]:
    """Most recent `limit` live messages, returned oldest->newest. Soft-deleted
    turns are excluded (see soft_delete)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE deleted_at IS NULL "
            "ORDER BY turn DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def messages_before(before_turn: int, limit: int) -> list[dict]:
    """The `limit` live messages immediately older than `before_turn` (turn
    strictly less than it), returned oldest->newest. Keyset page for chat
    scroll-up; soft-deleted turns are skipped."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE turn < ? AND deleted_at IS NULL "
            "ORDER BY turn DESC LIMIT ?",
            (before_turn, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_message(message_id: int) -> dict | None:
    """A single live message by id. Returns None for a soft-deleted turn, which
    is also how retrieval skips deleted anchors for free (see chat.retrieval)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM messages WHERE id = ? AND deleted_at IS NULL",
            (message_id,),
        ).fetchone()
    return dict(row) if row else None


def messages_in_turn_range(start_turn: int, end_turn: int) -> list[dict]:
    """Live messages whose turn is in [start, end]. Soft-deleted turns drop out
    of the window, so they never resurface as retrieval neighbours either."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE turn BETWEEN ? AND ? "
            "AND deleted_at IS NULL ORDER BY turn",
            (start_turn, end_turn),
        ).fetchall()
    return [dict(r) for r in rows]


def soft_delete(turn: int) -> bool:
    """Mark a turn deleted so it vanishes from every model-facing read path while
    its row, turn, and vector stay intact (reversible). Returns True if this call
    marked a previously-live turn, False if the turn is unknown or already gone."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE messages SET deleted_at = datetime('now') "
            "WHERE turn = ? AND deleted_at IS NULL",
            (turn,),
        )
        return cur.rowcount > 0


def max_turn() -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COALESCE(MAX(turn), -1) AS t FROM messages"
        ).fetchone()["t"]


def add_summary(start_turn: int, end_turn: int, content: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO summaries(start_turn, end_turn, content) VALUES (?, ?, ?)",
            (start_turn, end_turn, content),
        )
        return cur.lastrowid


def list_summaries(limit: int, before_id: int | None = None) -> list[dict]:
    """Summary 'cards' newest-first (id desc). When `before_id` is given, only
    those with id strictly less than it — keyset page for the diary timeline."""
    with get_conn() as conn:
        if before_id is None:
            rows = conn.execute(
                "SELECT * FROM summaries ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM summaries WHERE id < ? ORDER BY id DESC LIMIT ?",
                (before_id, limit),
            ).fetchall()
    return [dict(r) for r in rows]


def get_summary(summary_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,)).fetchone()
    return dict(row) if row else None


def add_vector_ref(ref_type: str, ref_id: int) -> int:
    """Allocate an HNSW label bound to a source row. Returns the label."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO vector_refs(ref_type, ref_id) VALUES (?, ?)",
            (ref_type, ref_id),
        )
        return cur.lastrowid


def resolve_vector_ref(label: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ref_type, ref_id FROM vector_refs WHERE label = ?", (label,)
        ).fetchone()
    return dict(row) if row else None


def get_cursor(concern: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT through_turn FROM cursors WHERE concern = ?", (concern,)
        ).fetchone()
    return row["through_turn"] if row else -1


def advance_cursor(concern: str, through_turn: int) -> None:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE cursors SET through_turn = ?, updated_at = datetime('now') "
            "WHERE concern = ?",
            (through_turn, concern),
        )
        if cur.rowcount == 0:
            raise ValueError(f"Unknown cursor concern: {concern!r}")
