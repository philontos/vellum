"""Persistence for conversation-eval Prompt versions, archives, and runs."""
import json

from app.store.observability import get_conn


def create_prompt_version(name: str, content: str) -> dict:
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO conversation_eval_prompt_versions(name, content) VALUES (?, ?)",
            (name, content),
        )
        row = conn.execute(
            "SELECT * FROM conversation_eval_prompt_versions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def list_prompt_versions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_eval_prompt_versions ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_prompt_version(version_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversation_eval_prompt_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
    return dict(row) if row else None


_RECORD_FIELDS = (
    "source_user_turn", "source_assistant_turn", "stream", "source_created_at",
    "source_user_content", "baseline_output", "baseline_prompt_release_id",
    "baseline_prompt_release_version", "baseline_prompt_label",
    "baseline_system_prompt", "baseline_input_json", "prompt_kind",
    "prompt_release_id", "prompt_release_version", "prompt_version_id",
    "prompt_label", "system_prompt", "input_json", "runtime_snapshot_json",
)


def _record_row(row) -> dict:
    item = dict(row)
    for stored, exposed in (
        ("baseline_input_json", "baseline_input"),
        ("input_json", "input"),
        ("runtime_snapshot_json", "runtime_snapshot"),
    ):
        raw = item.pop(stored)
        item[exposed] = json.loads(raw) if raw else None
    return item


def create_record(record: dict) -> dict:
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO conversation_eval_records("
            + ",".join(_RECORD_FIELDS) + ") VALUES ("
            + ",".join("?" for _ in _RECORD_FIELDS) + ")",
            tuple(record.get(field) for field in _RECORD_FIELDS),
        )
        row = conn.execute(
            "SELECT * FROM conversation_eval_records WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _record_row(row)


def get_record(record_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversation_eval_records WHERE id = ?", (record_id,),
        ).fetchone()
    return _record_row(row) if row else None


def list_records(limit: int = 50, before: int | None = None) -> list[dict]:
    where = "WHERE r.id < ?" if before is not None else ""
    params = (before, limit) if before is not None else (limit,)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT r.id, r.source_user_turn, r.source_assistant_turn, r.stream, "
            "substr(r.source_user_content, 1, 500) AS source_user_content, "
            "substr(r.baseline_output, 1, 500) AS baseline_output, "
            "r.baseline_prompt_label, "
            "r.prompt_kind, r.prompt_release_id, r.prompt_release_version, "
            "r.prompt_version_id, r.prompt_label, r.created_at, "
            "(SELECT COUNT(*) FROM conversation_eval_runs run "
            " WHERE run.record_id = r.id) AS run_count, "
            "(SELECT status FROM conversation_eval_runs run "
            " WHERE run.record_id = r.id ORDER BY run.id DESC LIMIT 1) AS latest_status, "
            "(SELECT substr(output, 1, 500) FROM conversation_eval_runs run "
            " WHERE run.record_id = r.id ORDER BY run.id DESC LIMIT 1) AS latest_output "
            "FROM conversation_eval_records r " + where + " ORDER BY r.id DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


_RUN_FIELDS = (
    "record_id", "source_user_turn", "source_assistant_turn", "stream",
    "source_user_content", "original_content", "prompt_kind",
    "prompt_release_id", "prompt_release_version", "prompt_version_id",
    "prompt_label", "system_prompt", "input_json", "model",
)


def create_run(record: dict) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO conversation_eval_runs(" + ",".join(_RUN_FIELDS) + ") "
            "VALUES (" + ",".join("?" for _ in _RUN_FIELDS) + ")",
            tuple(record.get(field) for field in _RUN_FIELDS),
        )
        return cursor.lastrowid


def finish_run(
    run_id: int, *, output: str, reasoning: str | None,
    tool_calls: list[dict] | None, prompt_tokens: int | None,
    completion_tokens: int | None, duration_ms: int | None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversation_eval_runs SET status = 'done', output = ?, "
            "reasoning = ?, tool_calls_json = ?, prompt_tokens = ?, "
            "completion_tokens = ?, duration_ms = ?, error = NULL, "
            "finished_at = datetime('now') WHERE id = ?",
            (
                output, reasoning,
                json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                prompt_tokens, completion_tokens, duration_ms, run_id,
            ),
        )


def fail_run(run_id: int, error: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversation_eval_runs SET status = 'error', error = ?, "
            "finished_at = datetime('now') WHERE id = ?",
            (error, run_id),
        )


def _run_row(row) -> dict:
    item = dict(row)
    raw_tools = item.pop("tool_calls_json")
    item["tool_calls"] = json.loads(raw_tools) if raw_tools else None
    # The record owns the immutable Prompt/input snapshot; result cards stay small.
    for field in (
        "system_prompt", "input_json", "source_user_content",
        "original_content", "reasoning",
    ):
        item.pop(field, None)
    return item


def get_run(run_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversation_eval_runs WHERE id = ?", (run_id,),
        ).fetchone()
    return _run_row(row) if row else None


def runs_for_record(record_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_eval_runs WHERE record_id = ? ORDER BY id DESC",
            (record_id,),
        ).fetchall()
    return [_run_row(row) for row in rows]
