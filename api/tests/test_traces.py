from app.store import traces
from app.store.observability import get_conn


def _record(stage="chat", pinned=False, reasoning="chain of thought"):
    return traces.record(
        turn=1, stage=stage, model="m", params={"t": 0.7},
        prompt="big prompt", output="big output", reasoning=reasoning,
        prompt_tokens=10, completion_tokens=20, duration_ms=5, pinned=pinned,
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
