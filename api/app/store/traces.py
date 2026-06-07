"""Observability DAO: raw LLM-call traces. Diagnostic exhaust — not memory,
not retrieved, not modeled. Retention = rolling window of heavy fields
(prompt/output) + forever-metadata; prune nulls heavy fields but keeps the row;
pinned rows are spared."""
import json

from app.store.db import get_conn


def record(*, turn, stage, model, params, prompt, output,
           prompt_tokens, completion_tokens, duration_ms, reasoning=None,
           pinned=False) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO traces(turn, stage, model, params, prompt, output, "
            "reasoning, prompt_tokens, completion_tokens, duration_ms, pinned) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (turn, stage, model, json.dumps(params, ensure_ascii=False),
             prompt, output, reasoning, prompt_tokens, completion_tokens,
             duration_ms, 1 if pinned else 0),
        )
        return cur.lastrowid


def prune(keep_last: int) -> None:
    """Null out prompt/output/reasoning on all but the most recent `keep_last`
    unpinned rows. Rows (and their lightweight metadata) are always kept."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE traces SET prompt = NULL, output = NULL, reasoning = NULL "
            "WHERE pinned = 0 AND prompt IS NOT NULL AND id NOT IN ("
            "  SELECT id FROM traces WHERE pinned = 0 ORDER BY id DESC LIMIT ?"
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
    with get_conn() as conn:
        if stage:
            rows = conn.execute(
                "SELECT * FROM traces WHERE stage = ? ORDER BY id DESC LIMIT ?",
                (stage, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM traces ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def set_note(trace_id: int, note: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE traces SET note = ? WHERE id = ?", (note, trace_id))
