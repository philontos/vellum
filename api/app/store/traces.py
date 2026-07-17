"""Observability DAO: raw LLM-call traces. Diagnostic exhaust — not memory,
not retrieved, not modeled. Lives in observability.db (see app.store.observability).
Retention = rolling window of heavy fields (prompt/output) + forever-metadata;
prune nulls heavy fields but keeps the row; pinned rows are spared. Eval traces
(eval_run_id IS NOT NULL) are NEVER pruned — they're durable observation tied to
their run, deleted only when the run is."""
import json

from app.store.observability import get_conn


def record(*, turn, stage, model, params, prompt, output,
           prompt_tokens, completion_tokens, duration_ms, reasoning=None,
           pinned=False, eval_run_id=None, eval_case=None,
           tool_calls=None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO traces(turn, stage, model, params, prompt, output, "
            "reasoning, prompt_tokens, completion_tokens, duration_ms, pinned, "
            "eval_run_id, eval_case, tool_calls) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (turn, stage, model, json.dumps(params, ensure_ascii=False),
             prompt, output, reasoning, prompt_tokens, completion_tokens,
             duration_ms, 1 if pinned else 0, eval_run_id, eval_case,
             json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None),
        )
        return cur.lastrowid


def prune(keep_last: int) -> None:
    """Null out prompt/output/reasoning/tool_calls on all but the most recent
    `keep_last` unpinned CHAT traces. Eval traces (eval_run_id IS NOT NULL) are
    exempt — kept in full until their run is deleted. Rows (and lightweight
    metadata) always kept."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE traces SET prompt = NULL, output = NULL, reasoning = NULL, "
            "tool_calls = NULL "
            "WHERE pinned = 0 AND eval_run_id IS NULL AND prompt IS NOT NULL "
            "AND id NOT IN ("
            "  SELECT id FROM traces WHERE pinned = 0 AND eval_run_id IS NULL "
            "  ORDER BY id DESC LIMIT ?"
            ")",
            (keep_last,),
        )


def pin(trace_id: int, pinned: bool = True) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE traces SET pinned = ? WHERE id = ?",
            (1 if pinned else 0, trace_id),
        )


def list_recent(limit: int = 100, stage: str | None = None) -> list[dict]:
    """Recent CHAT traces (eval traces excluded — view those per run via
    app.store.observability.traces_for_run)."""
    with get_conn() as conn:
        if stage:
            rows = conn.execute(
                "SELECT * FROM traces WHERE eval_run_id IS NULL AND stage = ? "
                "ORDER BY id DESC LIMIT ?",
                (stage, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM traces WHERE eval_run_id IS NULL "
                "ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def _last_user_snippet(prompt: str | None) -> str | None:
    if not prompt:
        return None
    try:
        messages = json.loads(prompt)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if (
            isinstance(message, dict)
            and message.get("role") == "user"
            and isinstance(message.get("content"), str)
        ):
            return message["content"]
    return None


def list_summaries(limit: int = 100, stage: str | None = None) -> list[dict]:
    """Return scan-friendly metadata without multi-megabyte trace bodies.

    The full prompt/output/reasoning/tool payload is fetched only when one row is
    expanded. ``prompt`` is selected locally solely to derive the latest user
    snippet and is removed before the response leaves the process.
    """
    where = "eval_run_id IS NULL"
    params: list[object] = []
    if stage:
        where += " AND stage = ?"
        params.append(stage)
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, turn, stage, model, params, prompt, prompt_tokens, "
            "completion_tokens, duration_ms, pinned, note, created_at, "
            "reasoning IS NOT NULL AS has_reasoning, "
            "tool_calls IS NOT NULL AS has_tool_calls "
            f"FROM traces WHERE {where} ORDER BY id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    summaries = []
    for row in rows:
        summary = dict(row)
        summary["snippet"] = _last_user_snippet(summary.pop("prompt"))
        summary["has_reasoning"] = bool(summary["has_reasoning"])
        summary["has_tool_calls"] = bool(summary["has_tool_calls"])
        summaries.append(summary)
    return summaries


def get_by_id(trace_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM traces WHERE id = ? AND eval_run_id IS NULL",
            (trace_id,),
        ).fetchone()
    return dict(row) if row else None


def set_note(trace_id: int, note: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE traces SET note = ? WHERE id = ?", (note, trace_id))
