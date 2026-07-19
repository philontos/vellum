"""Read-only DAO for production turn roots and their correlated trace rows."""
import json
from typing import Any

from app.store.observability import get_conn


def _decode_json(raw: Any) -> Any:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return raw
    return value if isinstance(value, (dict, list)) else raw


def _decode_run(row) -> dict:
    item = dict(row)
    item["decision"] = _decode_json(item.pop("decision_json"))
    context = _decode_json(item.pop("context_meta_json"))
    item["context_meta"] = context if isinstance(context, dict) else {}
    return item


def _where(
    *,
    status: str | None,
    route: str | None,
    stream: str | None,
    user_turn: int | None,
    assistant_turn: int | None,
    started_after: str | None,
    started_before: str | None,
) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    for column, value in (
        ("status", status),
        ("route", route),
        ("stream", stream),
        ("user_turn", user_turn),
        ("assistant_turn", assistant_turn),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)
    if started_after is not None:
        clauses.append("started_at >= ?")
        params.append(started_after)
    if started_before is not None:
        clauses.append("started_at <= ?")
        params.append(started_before)
    return ("WHERE " + " AND ".join(clauses) if clauses else ""), params


def load_window(
    *,
    limit: int,
    status: str | None = None,
    route: str | None = None,
    stream: str | None = None,
    user_turn: int | None = None,
    assistant_turn: int | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """Load bounded roots and lightweight span metadata in two queries."""
    where, params = _where(
        status=status,
        route=route,
        stream=stream,
        user_turn=user_turn,
        assistant_turn=assistant_turn,
        started_after=started_after,
        started_before=started_before,
    )
    with get_conn() as conn:
        run_rows = conn.execute(
            f"SELECT * FROM turn_runs {where} "
            "ORDER BY started_at DESC, rowid DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        runs = [_decode_run(row) for row in run_rows]
        if not runs:
            return [], []
        placeholders = ",".join("?" for _ in runs)
        span_rows = conn.execute(
            "SELECT id, run_id, stage, model, params, prompt_tokens, "
            "completion_tokens, duration_ms, attempt, "
            "prompt IS NOT NULL AS has_prompt, "
            "output IS NOT NULL AS has_output "
            "FROM traces WHERE eval_run_id IS NULL "
            f"AND run_id IN ({placeholders}) ORDER BY id",
            tuple(run["id"] for run in runs),
        ).fetchall()
    return runs, [dict(row) for row in span_rows]


def get(run_id: str) -> tuple[dict, list[dict]] | None:
    """Load one root and full spans in call order."""
    with get_conn() as conn:
        run_row = conn.execute(
            "SELECT * FROM turn_runs WHERE id = ?", (run_id,),
        ).fetchone()
        if run_row is None:
            return None
        span_rows = conn.execute(
            "SELECT id, turn, stage, model, params, prompt, output, reasoning, "
            "prompt_tokens, completion_tokens, duration_ms, pinned, note, "
            "tool_calls, run_id, scenario, attempt, created_at "
            "FROM traces WHERE eval_run_id IS NULL AND run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
    spans = []
    for row in span_rows:
        item = dict(row)
        for field in ("params", "prompt", "tool_calls"):
            item[field] = _decode_json(item[field])
        spans.append(item)
    return _decode_run(run_row), spans
