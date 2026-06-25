import json

from app.config import observability_db_path
from app.store import crypto, observability, traces
from app.store.observability import get_conn

SAMPLE_CALLS = [
    {"name": "web_search", "args": {"query": "weather today"},
     "result": "It is sunny.", "ok": True},
    {"name": "recall_memory", "args": {"query": "birthday"},
     "result": "ERROR no match", "ok": False},
]


def _record(stage="chat", pinned=False, reasoning="chain of thought",
            tool_calls=None):
    return traces.record(
        turn=1, stage=stage, model="m", params={"t": 0.7},
        prompt="big prompt", output="big output", reasoning=reasoning,
        prompt_tokens=10, completion_tokens=20, duration_ms=5, pinned=pinned,
        tool_calls=tool_calls,
    )


def test_record_persists_full_fields(migrated_db):
    tid = _record()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row["prompt"] == "big prompt" and row["output"] == "big output"
    assert row["reasoning"] == "chain of thought"
    assert row["completion_tokens"] == 20


def test_reasoning_defaults_to_null(migrated_db):
    tid = _record(reasoning=None)            # non-reasoning model
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row["reasoning"] is None


def test_prune_nulls_heavy_fields_keeps_row_and_metadata(migrated_db):
    tid = _record()
    traces.prune(keep_last=0)            # prune everything eligible
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row is not None               # row survives
    assert row["prompt"] is None and row["output"] is None   # heavy fields cleared
    assert row["reasoning"] is None      # reasoning is heavy too — cleared
    assert row["prompt_tokens"] == 10    # metadata kept


def test_prune_spares_pinned(migrated_db):
    tid = _record(pinned=True)
    traces.prune(keep_last=0)
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row["prompt"] == "big prompt"  # pinned heavy fields untouched


def test_prune_keeps_last_n(migrated_db):
    ids = [_record(stage=f"s{i}") for i in range(5)]
    traces.prune(keep_last=2)
    with get_conn() as conn:
        rows = {r["id"]: r for r in conn.execute("SELECT * FROM traces").fetchall()}
    for i in range(3):
        assert rows[ids[i]]["prompt"] is None
    for i in range(3, 5):
        assert rows[ids[i]]["prompt"] == "big prompt"


def test_record_persists_tool_calls(migrated_db):
    tid = _record(tool_calls=SAMPLE_CALLS)
    with get_conn() as conn:
        row = conn.execute("SELECT tool_calls FROM traces WHERE id = ?", (tid,)).fetchone()
    assert json.loads(row["tool_calls"]) == SAMPLE_CALLS


def test_tool_calls_default_to_null(migrated_db):
    tid = _record()                          # turn with no tool activity
    with get_conn() as conn:
        row = conn.execute("SELECT tool_calls FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row["tool_calls"] is None


def test_prune_nulls_tool_calls(migrated_db):
    tid = _record(tool_calls=SAMPLE_CALLS)   # tool_calls is heavy — pruned with the rest
    traces.prune(keep_last=0)
    with get_conn() as conn:
        row = conn.execute("SELECT tool_calls FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row["tool_calls"] is None


# Pre-feature traces table (every current column except tool_calls) — what a
# deployed observability.db looks like before this change. Connecting through
# the module must add the column with no migration runner.
_LEGACY_TRACES = """
CREATE TABLE traces (
  id INTEGER PRIMARY KEY AUTOINCREMENT, turn INTEGER, stage TEXT NOT NULL,
  model TEXT, params TEXT, prompt TEXT, output TEXT, reasoning TEXT,
  prompt_tokens INTEGER, completion_tokens INTEGER, duration_ms INTEGER,
  pinned INTEGER NOT NULL DEFAULT 0, note TEXT, eval_run_id INTEGER,
  eval_case TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def test_migration_adds_tool_calls_to_legacy_db(migrated_db):
    p = observability_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = crypto.sqlite_module().connect(str(p))
    crypto.apply_key(conn)
    conn.executescript(_LEGACY_TRACES)
    conn.commit()
    conn.close()
    observability._initialized.discard(str(p))   # force schema re-init on next connect

    tid = _record(tool_calls=SAMPLE_CALLS)        # would fail if the column were missing
    with get_conn() as conn:
        row = conn.execute("SELECT tool_calls FROM traces WHERE id = ?", (tid,)).fetchone()
    assert json.loads(row["tool_calls"]) == SAMPLE_CALLS
