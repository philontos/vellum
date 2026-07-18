"""Root records that correlate every span of one orchestrated chat turn."""
import json

from app.store.observability import get_conn


def _decode(row) -> dict | None:
    if row is None:
        return None
    item = dict(row)
    decision_json = item.pop("decision_json")
    item["decision"] = json.loads(decision_json) if decision_json else None
    item["context_meta"] = json.loads(item.pop("context_meta_json") or "{}")
    return item


def start(
    *, run_id: str, user_turn: int, stream: str, context_meta: dict,
    prompt_release_id: int | None, prompt_release_version: int | None,
) -> dict:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO turn_runs("
            "id,user_turn,stream,status,context_meta_json,prompt_release_id,"
            "prompt_release_version) VALUES (?, ?, ?, 'running', ?, ?, ?)",
            (
                run_id, user_turn, stream,
                json.dumps(context_meta, ensure_ascii=False),
                prompt_release_id, prompt_release_version,
            ),
        )
    return get(run_id)


def finish(
    *, run_id: str, assistant_turn: int, route: str, status: str,
    inquiry_id: int | None, revision_before: int | None,
    revision_after: int | None, controller_model: str | None,
    responder_model: str | None, decision: dict, error: str | None,
) -> dict:
    if status not in {"done", "degraded"}:
        raise ValueError(f"Invalid completed turn status {status!r}")
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE turn_runs SET assistant_turn = ?, route = ?, status = ?, "
            "inquiry_id = ?, revision_before = ?, revision_after = ?, "
            "controller_model = ?, responder_model = ?, decision_json = ?, "
            "error = ?, finished_at = datetime('now') WHERE id = ?",
            (
                assistant_turn, route, status, inquiry_id, revision_before,
                revision_after, controller_model, responder_model,
                json.dumps(decision, ensure_ascii=False), error, run_id,
            ),
        )
        if cur.rowcount != 1:
            raise KeyError(run_id)
    return get(run_id)


def fail(run_id: str, error: str) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE turn_runs SET status = 'error', error = ?, "
            "finished_at = datetime('now') WHERE id = ?",
            (error[:2_000], run_id),
        )
        if cur.rowcount != 1:
            raise KeyError(run_id)
    return get(run_id)


def get(run_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM turn_runs WHERE id = ?", (run_id,),
        ).fetchone()
    return _decode(row)


def list_recent(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM turn_runs ORDER BY started_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_decode(row) for row in rows]
