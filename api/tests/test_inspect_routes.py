import json

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


def test_inspect_model_attaches_trait_meta(migrated_db):
    from app.main import app
    from app.store import model
    model.set_trait("mbti", {"E_I": {"score": 64}}, 1)

    c = TestClient(app)
    traits = c.get("/inspect/model").json()["traits"]
    mbti = next(t for t in traits if t["dimension"] == "mbti")
    assert mbti["meta"]["name"]
    e_i = next(s for s in mbti["meta"]["sub_dimensions"] if s["key"] == "E_I")
    assert e_i["poles"] == ["I", "E"]


def test_trace_list_is_lightweight_and_detail_is_loaded_separately(migrated_db):
    from app.main import app
    from app.store import traces

    prompt = json.dumps([
        {"role": "system", "content": "x" * 10_000},
        {"role": "user", "content": "the newest user question"},
    ])
    tid = traces.record(
        turn=3,
        stage="chat",
        model="m",
        params={"stream": "neutral"},
        prompt=prompt,
        output="y" * 10_000,
        reasoning="reasoning",
        prompt_tokens=10,
        completion_tokens=20,
        duration_ms=30,
        tool_calls=[{"name": "memory", "ok": True}],
    )

    client = TestClient(app)
    summary = client.get("/inspect/traces?limit=100").json()["traces"][0]

    assert summary["id"] == tid
    assert summary["snippet"] == "the newest user question"
    assert summary["has_reasoning"] is True
    assert summary["has_tool_calls"] is True
    assert "prompt" not in summary
    assert "output" not in summary
    assert "reasoning" not in summary
    assert "tool_calls" not in summary

    detail_response = client.get(f"/inspect/traces/{tid}")
    assert detail_response.status_code == 200
    detail = detail_response.json()["trace"]
    assert detail["prompt"] == prompt
    assert detail["output"] == "y" * 10_000
    assert detail["reasoning"] == "reasoning"
    assert json.loads(detail["tool_calls"])[0]["name"] == "memory"

    assert client.get("/inspect/traces/999999").status_code == 404


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
