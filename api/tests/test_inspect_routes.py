from fastapi.testclient import TestClient


def test_inspect_model_and_traces(migrated_db):
    from app.main import app
    from app.store import model, traces
    model.set_dossier("who you are")
    model.add_fact("allergic to penicillin")
    model.set_trait("ocean", {"O": {"score": 72}}, 1)
    tid = traces.record(turn=1, stage="trait", model="m", params={}, prompt="p",
                        output="o", prompt_tokens=1, completion_tokens=1, duration_ms=1)

    c = TestClient(app)
    m = c.get("/inspect/model").json()
    assert m["dossier"] == "who you are"
    assert any(f["text"] == "allergic to penicillin" for f in m["facts"])
    assert m["traits"][0]["dimension"] == "ocean"
    assert "history" in m["traits"][0]

    t = c.get("/inspect/traces?stage=trait").json()["traces"]
    assert t[0]["id"] == tid and t[0]["stage"] == "trait"

    r = c.post(f"/inspect/traces/{tid}", json={"pinned": True, "note": "good"})
    assert r.status_code == 200
    row = c.get("/inspect/traces").json()["traces"][0]
    assert row["pinned"] == 1 and row["note"] == "good"


def test_inspect_model_excludes_superseded_facts(migrated_db):
    from app.main import app
    from app.store import model
    model.add_fact("active fact")
    gone = model.add_fact("merged away")
    model.supersede_fact(gone)

    c = TestClient(app)
    facts = c.get("/inspect/model").json()["facts"]
    texts = {f["text"] for f in facts}
    assert "active fact" in texts
    assert "merged away" not in texts
