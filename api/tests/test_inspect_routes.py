import json

from fastapi.testclient import TestClient


def test_inspect_model_and_traces(migrated_db):
    from app.main import app
    from app.store import model, portrait_claims, traces
    model.set_dossier("who you are")
    model.add_fact("allergic to penicillin")
    portrait_claims.add(
        claim_type="value", text="Values accuracy.", basis="explicit",
        evidence=[{"turn": 1, "quote": "be accurate"}], source_turn=1,
    )
    model.set_trait("ocean", {"O": {"score": 72}}, 1)
    tid = traces.record(turn=1, stage="trait", model="m", params={}, prompt="p",
                        output="o", prompt_tokens=1, completion_tokens=1, duration_ms=1)

    c = TestClient(app)
    m = c.get("/inspect/model").json()
    assert m["dossier"] == "who you are"
    assert any(f["text"] == "allergic to penicillin" for f in m["facts"])
    assert m["portrait_claims"][0]["text"] == "Values accuracy."
    assert m["portrait_claims"][0]["evidence"][0]["turn"] == 1
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


def test_inspect_model_attaches_grounded_trait_observations(migrated_db):
    from app.main import app
    from app.store import model

    model.apply_trait_batch(
        dimension="ocean", start_turn=4, end_turn=8,
        observations=[{
            "sub_dimension": "O", "score": 82, "confidence": 0.7,
            "evidence_turn": 6, "evidence_quote": "我喜欢尝试陌生方法",
        }],
        content={"O": {"score": 72, "tau": 1.49, "confidence": 0.23}},
        sample_count=1,
    )

    traits = TestClient(app).get("/inspect/model").json()["traits"]
    ocean = next(item for item in traits if item["dimension"] == "ocean")

    assert ocean["observations"][0]["evidence_turn"] == 6
    assert ocean["observations"][0]["evidence_quote"] == "我喜欢尝试陌生方法"


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


def test_inquiry_question_trace_uses_current_user_turn_as_snippet(migrated_db):
    from app.main import app
    from app.store import traces

    prompt = json.dumps({
        "current_user_turn": {
            "turn": 12,
            "role": "user",
            "content": "我是不是应该辞职？",
        },
        "inquiry": None,
    }, ensure_ascii=False)
    traces.record(
        turn=13,
        stage="chat",
        model="m",
        params={"route": "inquire"},
        prompt=prompt,
        output="最近发生的哪件事让你最确定？",
        prompt_tokens=None,
        completion_tokens=None,
        duration_ms=20,
    )

    summary = TestClient(app).get("/inspect/traces").json()["traces"][0]

    assert summary["snippet"] == "我是不是应该辞职？"


def test_controller_only_trace_uses_current_user_turn_as_snippet(migrated_db):
    from app.main import app
    from app.store import traces

    prompt = json.dumps({
        "system_prompt": "controller",
        "user_prompt": json.dumps({
            "decision_schema": {},
            "context": {
                "current_user_turn": {
                    "turn": 12,
                    "role": "user",
                    "content": "The responder later failed.",
                },
                "inquiry": None,
            },
        }),
    })
    traces.record(
        turn=12,
        stage="inquiry.decide",
        model="controller",
        params={},
        prompt=prompt,
        output="{}",
        prompt_tokens=10,
        completion_tokens=2,
        duration_ms=20,
    )

    summary = TestClient(app).get("/inspect/traces").json()["traces"][0]

    assert summary["snippet"] == "The responder later failed."


def test_trace_list_classifies_legacy_trait_dimensions_from_structured_output(migrated_db):
    from app.main import app
    from app.store import traces

    outputs = {
        "ocean": {"O": None, "C": None, "E": None, "A": None, "N": None},
        "mbti": {"E_I": None, "S_N": None, "T_F": None, "J_P": None},
        "schwartz": {
            "achievement": None, "power": None, "hedonism": None,
            "stimulation": None, "self_direction": None, "universalism": None,
            "benevolence": None, "tradition": None, "conformity": None,
            "security": None,
        },
        "regulatory_focus": {"promotion": None, "prevention": None},
    }
    ids = {}
    for dimension, output in outputs.items():
        serialized = json.dumps(output)
        if dimension == "mbti":
            # Providers occasionally wrap otherwise valid JSON despite the
            # prompt's JSON-only instruction; the runtime accepts this shape.
            serialized = f"```json\n{serialized}\n```"
        ids[dimension] = traces.record(
            turn=3,
            stage="trait",
            model="m",
            params={},  # legacy rows did not persist the dimension context
            prompt="legacy configurable prompt",
            output=serialized,
            prompt_tokens=10,
            completion_tokens=20,
            duration_ms=30,
        )

    rows = TestClient(app).get("/inspect/traces?stage=trait").json()["traces"]
    by_id = {row["id"]: row for row in rows}

    for dimension, trace_id in ids.items():
        assert by_id[trace_id]["dimension"] == dimension
        assert "output" not in by_id[trace_id]


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


def test_inspect_model_exposes_complete_centered_schwartz_profile(migrated_db):
    from app.main import app
    from app.store import model

    model.set_trait("schwartz", {
        "achievement": {"score": 78, "tau": 8.0, "confidence": 0.7},
        "security": {"score": 76, "tau": 7.0, "confidence": 0.7},
        "conformity": {"score": 61, "tau": 3.0, "confidence": 0.4},
    }, sample_count=41)

    trait = next(
        item for item in TestClient(app).get("/inspect/model").json()["traits"]
        if item["dimension"] == "schwartz"
    )
    profile = trait["profile"]
    assert profile["kind"] == "schwartz_circumplex"
    assert profile["coverage"] == {"assessed": 3, "total": 10, "evidence_count": 3}
    assert list(profile["values"]) == [
        "self_direction", "stimulation", "hedonism", "achievement", "power",
        "security", "conformity", "tradition", "benevolence", "universalism",
    ]
    assert profile["values"]["tradition"]["status"] == "unobserved"
    assert len(profile["axes"]) == 2
