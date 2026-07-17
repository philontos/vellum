"""Memory layer DAO: the global message stream, conversation summaries,
HNSW label->source mapping, and per-concern modeling cursors."""
from app.store.db import get_conn


def append_message(role: str, content: str, stream: str = "neutral") -> dict:
    """Append to a stream's slice of the eternal stream; assign the next global
    turn. `turn` stays globally monotonic (unique across streams) so soft-delete,
    traces, and web turn ids are untouched; `stream` partitions the live context."""
    with get_conn() as conn:
        turn = conn.execute(
            "SELECT COALESCE(MAX(turn), -1) + 1 AS t FROM messages"
        ).fetchone()["t"]
        cur = conn.execute(
            "INSERT INTO messages(turn, role, content, stream) VALUES (?, ?, ?, ?)",
            (turn, role, content, stream),
        )
        return {"id": cur.lastrowid, "turn": turn}


def recent_tail(limit: int, stream: str = "neutral") -> list[dict]:
    """Most recent `limit` live messages in `stream`, returned oldest->newest.
    Soft-deleted turns are excluded (see soft_delete)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE stream = ? AND deleted_at IS NULL "
            "ORDER BY turn DESC LIMIT ?", (stream, limit)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def recent_tail_through(
    limit: int, through_turn: int, stream: str = "neutral",
) -> list[dict]:
    """Historical tail ending at ``through_turn`` (inclusive), oldest first.

    Conversation evals use this only when an old trace body is unavailable. The
    cutoff is important: replaying turn 20 must never quietly feed turns 21+ into
    the model just because they exist in today's database.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE stream = ? AND turn <= ? "
            "AND deleted_at IS NULL ORDER BY turn DESC LIMIT ?",
            (stream, through_turn, limit),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def conversation_rounds(
    limit: int, before: int | None = None,
) -> list[dict]:
    """Assistant turns paired with the nearest earlier user turn in their stream.

    The stream-local correlated lookup matters now that the global turn sequence
    interleaves modes. Results are newest first and keyset-paginated by assistant
    turn, which keeps a long private history cheap to browse.
    """
    before_sql = "AND a.turn < ?" if before is not None else ""
    args = ((before,) if before is not None else ()) + (limit,)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT "
            "u.id AS user_id, u.turn AS user_turn, u.content AS user_content, "
            "u.created_at AS user_created_at, "
            "a.id AS assistant_id, a.turn AS assistant_turn, "
            "a.content AS original_content, a.created_at AS created_at, a.stream "
            "FROM messages a "
            "JOIN messages u ON u.id = ("
            "  SELECT prior.id FROM messages prior "
            "  WHERE prior.stream = a.stream AND prior.turn < a.turn "
            "  ORDER BY prior.turn DESC LIMIT 1"
            ") "
            "WHERE a.role = 'assistant' AND a.deleted_at IS NULL "
            "AND u.role = 'user' AND u.deleted_at IS NULL "
            f"{before_sql} "
            "ORDER BY a.turn DESC LIMIT ?",
            args,
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation_round(assistant_turn: int) -> dict | None:
    rows = conversation_rounds(1, before=assistant_turn + 1)
    if rows and rows[0]["assistant_turn"] == assistant_turn:
        return rows[0]
    return None


def messages_before(before_turn: int, limit: int, stream: str = "neutral") -> list[dict]:
    """The `limit` live `stream` messages immediately older than `before_turn`
    (turn strictly less than it), returned oldest->newest. Keyset page for chat
    scroll-up; soft-deleted turns are skipped."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE stream = ? AND turn < ? AND deleted_at IS NULL "
            "ORDER BY turn DESC LIMIT ?",
            (stream, before_turn, limit),
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


def messages_in_turn_range(start_turn: int, end_turn: int,
                           stream: str | None = None) -> list[dict]:
    """Live messages whose turn is in [start, end]. Soft-deleted turns drop out of
    the window, so they never resurface as retrieval neighbours either. `stream`
    None spans all streams (the global modeling jobs co-build from every stream);
    a value scopes to one stream (per-stream summary digests + recall hydration)."""
    sql = ("SELECT * FROM messages WHERE turn BETWEEN ? AND ? AND deleted_at IS NULL"
           + (" AND stream = ?" if stream is not None else "")
           + " ORDER BY turn")
    args = (start_turn, end_turn) + ((stream,) if stream is not None else ())
    with get_conn() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def distinct_streams() -> list[str]:
    """Streams that have at least one live message — what the summary job iterates."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT stream FROM messages WHERE deleted_at IS NULL"
        ).fetchall()
    return [r["stream"] for r in rows]


def stream_turns_after(stream: str, after_turn: int) -> list[int]:
    """Live turn numbers in `stream` strictly newer than `after_turn`, ascending —
    the summary job's per-stream backlog (how many turns since its cursor)."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT turn FROM messages WHERE stream = ? AND turn > ? "
            "AND deleted_at IS NULL ORDER BY turn",
            (stream, after_turn),
        ).fetchall()
    return [r["turn"] for r in rows]


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


def add_summary(start_turn: int, end_turn: int, content: str,
                stream: str = "neutral") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO summaries(start_turn, end_turn, content, stream) VALUES (?, ?, ?, ?)",
            (start_turn, end_turn, content, stream),
        )
        return cur.lastrowid


def list_summaries(limit: int, before_id: int | None = None,
                   stream: str | None = None) -> list[dict]:
    """Summary 'cards' newest-first (id desc). When `before_id` is given, only
    those with id strictly less than it — keyset page for the diary timeline.
    `stream` None merges every stream into one timeline (the future unified view);
    a value scopes the diary to that mode. Each card carries its `stream` either way."""
    where = []
    args: list = []
    if before_id is not None:
        where.append("id < ?")
        args.append(before_id)
    if stream is not None:
        where.append("stream = ?")
        args.append(stream)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    args.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM summaries{clause} ORDER BY id DESC LIMIT ?", tuple(args)
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


def get_summary_cursor(stream: str) -> int:
    """Per-stream summary progress (own table — the global `cursors` CHECK forbids
    dynamic per-stream keys). Missing stream → -1, so its first turn is included."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT through_turn FROM summary_cursors WHERE stream = ?", (stream,)
        ).fetchone()
    return row["through_turn"] if row else -1


def advance_summary_cursor(stream: str, through_turn: int) -> None:
    """Upsert: a stream's cursor is created on its first summarized span."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO summary_cursors(stream, through_turn) VALUES (?, ?) "
            "ON CONFLICT(stream) DO UPDATE SET through_turn = excluded.through_turn, "
            "updated_at = datetime('now')",
            (stream, through_turn),
        )
