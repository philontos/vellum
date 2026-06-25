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


def set_note(trace_id: int, note: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE traces SET note = ? WHERE id = ?", (note, trace_id))
