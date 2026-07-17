"""Observability store: a dedicated DB (observability.db) for diagnostic traces
+ eval runs/results. Separate file from vellum.db so eval/observability data is
decoupled from the personal-model data and can be retained/consumed independently.

Schema is created lazily on first connect (CREATE TABLE IF NOT EXISTS) — there is
no separate migration runner for this DB. Columns added to an existing table
(CREATE IF NOT EXISTS can't grow one) are reconciled by `_ensure_columns` on the
same first-connect path. The `traces` table lives here (the raw trace DAO in
app.store.traces opens its connection through this module); offline suite runs
and conversation replay runs are the eval panel's durable records."""
import json
from contextlib import contextmanager

from app.config import observability_db_path
from app.store import crypto

_sqlite = crypto.sqlite_module()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  turn               INTEGER,
  stage              TEXT    NOT NULL,
  model              TEXT,
  params             TEXT,
  prompt             TEXT,
  output             TEXT,
  reasoning          TEXT,
  prompt_tokens      INTEGER,
  completion_tokens  INTEGER,
  duration_ms        INTEGER,
  pinned             INTEGER NOT NULL DEFAULT 0,
  note               TEXT,
  eval_run_id        INTEGER,           -- FK -> eval_runs.id; chat traces are NULL
  eval_case          TEXT,              -- case name for eval traces; chat traces NULL
  tool_calls         TEXT,              -- JSON [{name,args,result,ok}] for the turn; heavy, pruned
  created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_traces_created  ON traces(created_at);
CREATE INDEX IF NOT EXISTS idx_traces_eval_run ON traces(eval_run_id);

CREATE TABLE IF NOT EXISTS eval_runs (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  suite          TEXT    NOT NULL,
  status         TEXT    NOT NULL,        -- running|done|error
  model          TEXT,
  eval_model     TEXT,
  total          INTEGER NOT NULL DEFAULT 0,
  completed      INTEGER NOT NULL DEFAULT 0,
  aggregate_json TEXT,
  error          TEXT,
  started_at     TEXT    NOT NULL DEFAULT (datetime('now')),
  finished_at    TEXT
);

CREATE TABLE IF NOT EXISTS eval_results (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id      INTEGER NOT NULL,
  seq         INTEGER NOT NULL,
  case_name   TEXT    NOT NULL,
  status      TEXT    NOT NULL,           -- pass|fail|scored|error
  result_json TEXT,
  error       TEXT,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_eval_results_run ON eval_results(run_id);

CREATE TABLE IF NOT EXISTS conversation_eval_prompt_versions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT    NOT NULL,
  content     TEXT    NOT NULL,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conversation_eval_runs (
  id                       INTEGER PRIMARY KEY AUTOINCREMENT,
  source_user_turn         INTEGER NOT NULL,
  source_assistant_turn    INTEGER NOT NULL,
  stream                   TEXT    NOT NULL,
  source_user_content      TEXT    NOT NULL,
  original_content         TEXT    NOT NULL,
  prompt_kind              TEXT    NOT NULL,
  prompt_release_id        INTEGER,
  prompt_release_version   INTEGER,
  prompt_version_id        INTEGER,
  prompt_label             TEXT    NOT NULL,
  system_prompt            TEXT    NOT NULL,
  input_json               TEXT    NOT NULL,
  model                    TEXT,
  status                   TEXT    NOT NULL DEFAULT 'running',
  output                   TEXT,
  reasoning                TEXT,
  tool_calls_json          TEXT,
  prompt_tokens            INTEGER,
  completion_tokens        INTEGER,
  duration_ms              INTEGER,
  error                    TEXT,
  created_at               TEXT    NOT NULL DEFAULT (datetime('now')),
  finished_at              TEXT,
  FOREIGN KEY (prompt_version_id) REFERENCES conversation_eval_prompt_versions(id)
);
CREATE INDEX IF NOT EXISTS idx_conversation_eval_runs_turn
  ON conversation_eval_runs(source_assistant_turn, id);
"""

_initialized: set[str] = set()


def discard_path(path) -> None:
    """Re-run schema reconciliation after an out-of-band DB replacement."""
    _initialized.discard(str(path))


def _ensure_columns(conn) -> None:
    """Add columns introduced after a DB was first created — CREATE TABLE IF NOT
    EXISTS leaves an existing table untouched, and there is no migration runner.
    Each ALTER is idempotent (gated on the live column set), so this is safe to
    run on every first connect."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(traces)")}
    if "tool_calls" not in cols:
        conn.execute("ALTER TABLE traces ADD COLUMN tool_calls TEXT")


def _connect() -> _sqlite.Connection:
    p = observability_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = _sqlite.connect(p)
    crypto.apply_key(conn)
    conn.row_factory = _sqlite.Row
    key = str(p)
    if key not in _initialized:
        conn.executescript(_SCHEMA)
        _ensure_columns(conn)
        conn.commit()
        _initialized.add(key)
    return conn


@contextmanager
def get_conn():
    """Short-lived connection to observability.db. Commits on clean exit, always
    closes. Schema is ensured on first connect per DB path."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# --- eval_runs DAO ---------------------------------------------------------

def create_run(suite: str, total: int, *, model: str | None = None,
               eval_model: str | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO eval_runs(suite, status, model, eval_model, total) "
            "VALUES (?, 'running', ?, ?, ?)",
            (suite, model, eval_model, total),
        )
        return cur.lastrowid


def set_total(run_id: int, total: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE eval_runs SET total = ? WHERE id = ?", (total, run_id))


def bump_completed(run_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE eval_runs SET completed = completed + 1 WHERE id = ?", (run_id,)
        )


def finish_run(run_id: int, status: str, aggregate: dict | None = None,
               error: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE eval_runs SET status = ?, aggregate_json = ?, error = ?, "
            "finished_at = datetime('now') WHERE id = ?",
            (status, json.dumps(aggregate, ensure_ascii=False) if aggregate is not None
             else None, error, run_id),
        )


def _run_row(r: _sqlite.Row) -> dict:
    d = dict(r)
    d["aggregate"] = json.loads(d.pop("aggregate_json")) if d.get("aggregate_json") else None
    return d


def list_runs(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM eval_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_run_row(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone()
    return _run_row(row) if row else None


# --- eval_results DAO ------------------------------------------------------

def add_result(run_id: int, seq: int, case_name: str, status: str,
               result: dict | None = None, error: str | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO eval_results(run_id, seq, case_name, status, result_json, error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, seq, case_name, status,
             json.dumps(result, ensure_ascii=False) if result is not None else None,
             error),
        )
        return cur.lastrowid


def _result_row(r: _sqlite.Row) -> dict:
    d = dict(r)
    d["result"] = json.loads(d.pop("result_json")) if d.get("result_json") else None
    return d


def results_for_run(run_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM eval_results WHERE run_id = ? ORDER BY seq", (run_id,)
        ).fetchall()
    return [_result_row(r) for r in rows]


def traces_for_run(run_id: int) -> list[dict]:
    """Eval traces captured during a run (newest first), for the panel drill-down."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM traces WHERE eval_run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# --- conversation replay evals --------------------------------------------

def create_conversation_prompt_version(name: str, content: str) -> dict:
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO conversation_eval_prompt_versions(name, content) "
            "VALUES (?, ?)",
            (name, content),
        )
        row = conn.execute(
            "SELECT * FROM conversation_eval_prompt_versions WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(row)


def list_conversation_prompt_versions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_eval_prompt_versions ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_conversation_prompt_version(version_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversation_eval_prompt_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
    return dict(row) if row else None


def create_conversation_run(record: dict) -> int:
    fields = (
        "source_user_turn", "source_assistant_turn", "stream",
        "source_user_content", "original_content", "prompt_kind",
        "prompt_release_id", "prompt_release_version", "prompt_version_id",
        "prompt_label", "system_prompt", "input_json", "model",
    )
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO conversation_eval_runs(" + ",".join(fields) + ") "
            "VALUES (" + ",".join("?" for _ in fields) + ")",
            tuple(record.get(field) for field in fields),
        )
        return cursor.lastrowid


def finish_conversation_run(
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


def fail_conversation_run(run_id: int, error: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversation_eval_runs SET status = 'error', error = ?, "
            "finished_at = datetime('now') WHERE id = ?",
            (error, run_id),
        )


def _conversation_run_row(row: _sqlite.Row) -> dict:
    item = dict(row)
    raw_tools = item.pop("tool_calls_json")
    item["tool_calls"] = json.loads(raw_tools) if raw_tools else None
    # The exact system/input snapshot remains durable for reproducibility, but
    # comparison cards do not need to transfer it on every refresh.
    item.pop("system_prompt", None)
    item.pop("input_json", None)
    item.pop("source_user_content", None)
    item.pop("original_content", None)
    item.pop("reasoning", None)
    return item


def get_conversation_run(run_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversation_eval_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _conversation_run_row(row) if row else None


def conversation_runs_for_turn(assistant_turn: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM conversation_eval_runs "
            "WHERE source_assistant_turn = ? ORDER BY id DESC",
            (assistant_turn,),
        ).fetchall()
    return [_conversation_run_row(row) for row in rows]
