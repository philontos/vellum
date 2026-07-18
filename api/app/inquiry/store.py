"""Account-scoped SQLite persistence for current Inquiry Ledgers and events."""
import json

from app.store.db import get_conn


class InquiryStoreError(RuntimeError):
    pass


class InquiryNotFoundError(InquiryStoreError):
    pass


class RevisionConflictError(InquiryStoreError):
    pass


class ClosedInquiryError(InquiryStoreError):
    pass


class ActiveInquiryExistsError(InquiryStoreError):
    pass


_STATUSES = {"exploring", "reviewing", "paused", "closed"}
_ACTIONS = {"open", "inquire", "synthesize", "resume", "pause", "close"}


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _inquiry(row) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    item["ledger"] = json.loads(item.pop("ledger_json"))
    return item


def _event(row) -> dict:
    item = dict(row)
    item["ledger"] = json.loads(item.pop("ledger_json"))
    item["decision"] = json.loads(item.pop("decision_json"))
    return item


def get(inquiry_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM inquiries WHERE id = ?", (inquiry_id,),
        ).fetchone()
    return _inquiry(row)


def get_current(stream: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM inquiries WHERE stream = ? AND status <> 'closed' "
            "ORDER BY CASE WHEN status = 'paused' THEN 1 ELSE 0 END, "
            "id DESC LIMIT 1",
            (stream,),
        ).fetchone()
    return _inquiry(row)


def get_active(stream: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM inquiries WHERE stream = ? "
            "AND status IN ('exploring','reviewing') ORDER BY id DESC LIMIT 1",
            (stream,),
        ).fetchone()
    return _inquiry(row)


def list_paused(stream: str, limit: int = 5) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM inquiries WHERE stream = ? AND status = 'paused' "
            "ORDER BY id DESC LIMIT ?", (stream, limit),
        ).fetchall()
    return [_inquiry(row) for row in rows]


def latest_for_stream(stream: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM inquiries WHERE stream = ? ORDER BY id DESC LIMIT 1",
            (stream,),
        ).fetchone()
    return _inquiry(row)


def list_recent(limit: int = 100, stream: str | None = None) -> list[dict]:
    where = "WHERE stream = ?" if stream is not None else ""
    args = ((stream,) if stream is not None else ()) + (limit,)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM inquiries {where} ORDER BY id DESC LIMIT ?", args,
        ).fetchall()
    return [_inquiry(row) for row in rows]


def list_events(inquiry_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM inquiry_events WHERE inquiry_id = ? "
            "ORDER BY revision_after", (inquiry_id,),
        ).fetchall()
    return [_event(row) for row in rows]


def get_by_run_id(run_id: str | None) -> dict | None:
    if run_id is None:
        return None
    with get_conn() as conn:
        event = conn.execute(
            "SELECT inquiry_id FROM inquiry_events WHERE run_id = ?", (run_id,),
        ).fetchone()
        if event is None:
            return None
        row = conn.execute(
            "SELECT * FROM inquiries WHERE id = ?", (event["inquiry_id"],),
        ).fetchone()
    return _inquiry(row)


def has_personality_modeling_blocker() -> bool:
    """Exploration/review stays provisional; pause/close is a safe boundary."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM inquiries "
            "WHERE status IN ('exploring','reviewing') LIMIT 1",
        ).fetchone()
    return row is not None


def _idempotent(conn, run_id: str | None) -> dict | None:
    if run_id is None:
        return None
    event = conn.execute(
        "SELECT inquiry_id FROM inquiry_events WHERE run_id = ?", (run_id,),
    ).fetchone()
    if event is None:
        return None
    return _inquiry(conn.execute(
        "SELECT * FROM inquiries WHERE id = ?", (event["inquiry_id"],),
    ).fetchone())


def open_inquiry(
    *, stream: str, opened_turn: int, ledger: dict, decision: dict,
    run_id: str | None, parent_inquiry_id: int | None = None,
) -> dict:
    goal = ((ledger.get("goal") or {}).get("text") or "").strip()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        replay = _idempotent(conn, run_id)
        if replay is not None:
            return replay
        current = conn.execute(
            "SELECT id FROM inquiries WHERE stream = ? "
            "AND status IN ('exploring','reviewing')",
            (stream,),
        ).fetchone()
        if current is not None:
            raise ActiveInquiryExistsError(
                f"Stream {stream!r} already has inquiry {current['id']}"
            )
        cur = conn.execute(
            "INSERT INTO inquiries("
            "stream,status,revision,goal,ledger_json,opened_turn,last_turn,"
            "parent_inquiry_id) VALUES (?, 'exploring', 1, ?, ?, ?, ?, ?)",
            (
                stream, goal, _dump(ledger), opened_turn, opened_turn,
                parent_inquiry_id,
            ),
        )
        inquiry_id = cur.lastrowid
        conn.execute(
            "INSERT INTO inquiry_events("
            "inquiry_id,run_id,user_turn,action,revision_before,revision_after,"
            "status_after,ledger_json,decision_json) "
            "VALUES (?, ?, ?, 'open', 0, 1, 'exploring', ?, ?)",
            (inquiry_id, run_id, opened_turn, _dump(ledger), _dump(decision)),
        )
        row = conn.execute(
            "SELECT * FROM inquiries WHERE id = ?", (inquiry_id,),
        ).fetchone()
    return _inquiry(row)


def apply_revision(
    *, inquiry_id: int, expected_revision: int, status: str, ledger: dict,
    action: str, user_turn: int, decision: dict, run_id: str | None,
) -> dict:
    if status not in _STATUSES:
        raise ValueError(f"Unknown inquiry status {status!r}")
    if action not in _ACTIONS:
        raise ValueError(f"Unknown inquiry action {action!r}")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        replay = _idempotent(conn, run_id)
        if replay is not None:
            return replay
        current = conn.execute(
            "SELECT * FROM inquiries WHERE id = ?", (inquiry_id,),
        ).fetchone()
        if current is None:
            raise InquiryNotFoundError(inquiry_id)
        if current["status"] == "closed":
            raise ClosedInquiryError(inquiry_id)
        if current["revision"] != expected_revision:
            raise RevisionConflictError(
                f"Expected revision {expected_revision}, found {current['revision']}"
            )
        next_revision = expected_revision + 1
        goal = ((ledger.get("goal") or {}).get("text") or "").strip()
        closed_turn = user_turn if status == "closed" else None
        conn.execute(
            "UPDATE inquiries SET status = ?, revision = ?, goal = ?, "
            "ledger_json = ?, last_turn = ?, closed_turn = ?, "
            "updated_at = datetime('now') WHERE id = ? AND revision = ?",
            (
                status, next_revision, goal, _dump(ledger), user_turn,
                closed_turn, inquiry_id, expected_revision,
            ),
        )
        conn.execute(
            "INSERT INTO inquiry_events("
            "inquiry_id,run_id,user_turn,action,revision_before,revision_after,"
            "status_after,ledger_json,decision_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                inquiry_id, run_id, user_turn, action, expected_revision,
                next_revision, status, _dump(ledger), _dump(decision),
            ),
        )
        row = conn.execute(
            "SELECT * FROM inquiries WHERE id = ?", (inquiry_id,),
        ).fetchone()
    return _inquiry(row)
