"""Observability store: a dedicated DB (observability.db) for diagnostic traces
+ eval runs/results. Separate file from vellum.db so eval/observability data is
decoupled from the personal-model data and can be retained/consumed independently.

Schema is created lazily on first connect (CREATE TABLE IF NOT EXISTS) — there is
no separate migration runner for this DB. Columns added to an existing table
(CREATE IF NOT EXISTS can't grow one) are reconciled by `_ensure_columns` on the
same first-connect path. The `traces` table lives here (the raw trace DAO in
app.store.traces opens its connection through this module); offline suite runs
and standalone conversation-evaluation archives are the eval panel's durable
records."""
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

CREATE TABLE IF NOT EXISTS conversation_eval_records (
  id                          INTEGER PRIMARY KEY AUTOINCREMENT,
  source_user_turn            INTEGER NOT NULL,
  source_assistant_turn       INTEGER NOT NULL,
  stream                      TEXT    NOT NULL,
  source_created_at           TEXT,
  source_user_content         TEXT    NOT NULL,
  baseline_output             TEXT    NOT NULL,
  baseline_prompt_release_id  INTEGER,
  baseline_prompt_release_version INTEGER,
  baseline_prompt_label       TEXT    NOT NULL,
  baseline_system_prompt      TEXT,
  baseline_input_json         TEXT,
  prompt_kind                 TEXT    NOT NULL,
  prompt_release_id           INTEGER,
  prompt_release_version      INTEGER,
  prompt_version_id           INTEGER,
  prompt_label                TEXT    NOT NULL,
  system_prompt               TEXT    NOT NULL,
  input_json                  TEXT    NOT NULL,
  runtime_snapshot_json       TEXT    NOT NULL,
  created_at                  TEXT    NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (prompt_version_id) REFERENCES conversation_eval_prompt_versions(id)
);
CREATE INDEX IF NOT EXISTS idx_conversation_eval_records_created
  ON conversation_eval_records(id);

CREATE TABLE IF NOT EXISTS conversation_eval_runs (
  id                       INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id                INTEGER,
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
    run_cols = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(conversation_eval_runs)")
    }
    if "record_id" not in run_cols:
        conn.execute("ALTER TABLE conversation_eval_runs ADD COLUMN record_id INTEGER")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversation_eval_runs_record "
        "ON conversation_eval_runs(record_id, id)"
    )


def _valid_json_object(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _baseline_from_trace(conn, assistant_turn: int) -> dict:
    trace = conn.execute(
        "SELECT params, prompt FROM traces WHERE eval_run_id IS NULL "
        "AND stage = 'chat' AND turn = ? ORDER BY id DESC LIMIT 1",
        (assistant_turn,),
    ).fetchone()
    if trace is None:
        return {
            "release_id": None, "release_version": None,
            "label": "Original Prompt", "system_prompt": None, "input_json": None,
        }
    params = _valid_json_object(trace["params"])
    version = params.get("prompt_release_version")
    label = f"Original · v{version}" if version is not None else "Original Prompt"
    input_json = trace["prompt"]
    system = None
    if input_json:
        try:
            messages = json.loads(input_json)
        except (TypeError, json.JSONDecodeError):
            messages = None
        if (
            isinstance(messages, list) and messages
            and isinstance(messages[0], dict)
            and messages[0].get("role") == "system"
            and isinstance(messages[0].get("content"), str)
        ):
            system = messages[0]["content"]
        else:
            input_json = None
    return {
        "release_id": params.get("prompt_release_id"),
        "release_version": version,
        "label": label,
        "system_prompt": system,
        "input_json": input_json,
    }


def _backfill_conversation_eval_records(conn) -> None:
    """Turn pre-archive replay runs into standalone records once, in place."""
    rows = conn.execute(
        "SELECT * FROM conversation_eval_runs WHERE record_id IS NULL ORDER BY id"
    ).fetchall()
    grouped: dict[tuple, int] = {}
    for row in rows:
        key = (
            row["source_assistant_turn"], row["prompt_kind"],
            row["prompt_release_id"], row["prompt_version_id"], row["system_prompt"],
        )
        record_id = grouped.get(key)
        if record_id is None:
            baseline = _baseline_from_trace(conn, row["source_assistant_turn"])
            cursor = conn.execute(
                "INSERT INTO conversation_eval_records("
                "source_user_turn, source_assistant_turn, stream, source_created_at, "
                "source_user_content, baseline_output, baseline_prompt_release_id, "
                "baseline_prompt_release_version, baseline_prompt_label, "
                "baseline_system_prompt, baseline_input_json, prompt_kind, "
                "prompt_release_id, prompt_release_version, prompt_version_id, "
                "prompt_label, system_prompt, input_json, runtime_snapshot_json, created_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["source_user_turn"], row["source_assistant_turn"], row["stream"],
                    row["created_at"], row["source_user_content"], row["original_content"],
                    baseline["release_id"], baseline["release_version"],
                    baseline["label"], baseline["system_prompt"], baseline["input_json"],
                    row["prompt_kind"], row["prompt_release_id"],
                    row["prompt_release_version"], row["prompt_version_id"],
                    row["prompt_label"], row["system_prompt"], row["input_json"],
                    "{}", row["created_at"],
                ),
            )
            record_id = cursor.lastrowid
            grouped[key] = record_id
        conn.execute(
            "UPDATE conversation_eval_runs SET record_id = ? WHERE id = ?",
            (record_id, row["id"]),
        )


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
        _backfill_conversation_eval_records(conn)
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
