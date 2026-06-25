"""Observability store: a dedicated DB (observability.db) for diagnostic traces
+ eval runs/results. Separate file from vellum.db so eval/observability data is
decoupled from the personal-model data and can be retained/consumed independently.

Schema is created lazily on first connect (CREATE TABLE IF NOT EXISTS) — there is
no separate migration runner for this DB. Columns added to an existing table
(CREATE IF NOT EXISTS can't grow one) are reconciled by `_ensure_columns` on the
same first-connect path. The `traces` table lives here (the raw trace DAO in
app.store.traces opens its connection through this module); eval_runs and
eval_results are the panel's durable records."""
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
"""

_initialized: set[str] = set()


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
