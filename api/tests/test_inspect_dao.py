from app.store import traces, model
from app.store.db import get_conn


def _rec(stage="trait"):
    return traces.record(turn=1, stage=stage, model="m", params={}, prompt="p",
                         output="o", prompt_tokens=1, completion_tokens=2, duration_ms=3)


def test_note_column_exists_and_settable(migrated_db):
    tid = _rec()
    traces.set_note(tid, "wrong fact")
    with get_conn() as conn:
        row = conn.execute("SELECT note FROM traces WHERE id=?", (tid,)).fetchone()
    assert row["note"] == "wrong fact"


def test_list_recent_filters_by_stage(migrated_db):
    _rec("facts"); _rec("trait"); _rec("facts")
    allrows = traces.list_recent(limit=10)
    factrows = traces.list_recent(limit=10, stage="facts")
    assert len(allrows) == 3 and len(factrows) == 2
    assert allrows[0]["id"] > allrows[-1]["id"]      # newest first


def test_all_facts_and_traits(migrated_db):
    model.add_fact("f1"); fid = model.add_fact("f2"); model.supersede_fact(fid)
    assert {f["text"] for f in model.all_facts()} == {"f1", "f2"}
    model.set_trait("ocean", {"O": {"score": 70}}, 1)
    rows = model.all_traits()
    assert rows[0]["dimension"] == "ocean" and rows[0]["content_json"]["O"]["score"] == 70
