"""Account-scoped persistence for time-sensitive, user-grounded state."""
import json

from app.store.db import get_conn


def _dump(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _row(row) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["snapshot"] = json.loads(item.pop("snapshot_json"))
    return item


def record(
    *, user_turn: int, stream: str, snapshot: dict,
    inquiry_id: int | None, run_id: str | None,
) -> dict | None:
    """Persist once per user turn; replaying the same orchestration is harmless."""
    if not (snapshot.get("states") or snapshot.get("deltas")):
        return None
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_state_snapshots("
            "stream, user_turn, inquiry_id, snapshot_json, run_id"
            ") VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_turn) DO NOTHING",
            (stream, user_turn, inquiry_id, _dump(snapshot), run_id),
        )
        row = conn.execute(
            "SELECT * FROM user_state_snapshots WHERE user_turn = ?",
            (user_turn,),
        ).fetchone()
    return _row(row)


def recent(
    *, limit: int = 8, before_turn: int | None = None,
    stream: str | None = None,
) -> list[dict]:
    clauses: list[str] = []
    args: list[object] = []
    if before_turn is not None:
        clauses.append("user_turn < ?")
        args.append(before_turn)
    if stream is not None:
        clauses.append("stream = ?")
        args.append(stream)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    args.append(max(0, limit))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM user_state_snapshots" + where
            + " ORDER BY user_turn DESC, id DESC LIMIT ?",
            tuple(args),
        ).fetchall()
    return [_row(row) for row in rows]
