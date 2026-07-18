import pytest

from app.model_loop import traits
from app.store import memory, model


@pytest.mark.asyncio
async def test_trait_job_updates_current_and_history(migrated_db, monkeypatch):
    # one strong OCEAN-openness signal for every dimension extract
    contexts = []
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        contexts.append(kw.get("context"))
        return {"O": {"score": 85, "confidence": 0.7, "evidence": "x"},
                "C": None, "E": None, "A": None, "N": None}
    monkeypatch.setattr(traits, "chat_json", fake_chat_json)
    # limit to one dimension to keep the test focused
    monkeypatch.setattr(traits, "DIMENSION_MAP",
                        {"ocean": traits.DIMENSION_MAP["ocean"]})

    memory.append_message("user", "I love trying brand-new experimental things")
    await traits.run(start_turn=0, end_turn=0)

    cur = model.get_trait("ocean")
    assert cur["content_json"]["O"]["score"] > 50
    assert len(model.get_trait_history("ocean")) == 1     # snapshot appended
    assert contexts == [{"dimension": "ocean"}]


@pytest.mark.asyncio
async def test_trait_null_signal_keeps_old(migrated_db, monkeypatch):
    model.set_trait("ocean", {"O": {"score": 70, "tau": 5.0, "confidence": 0.5}}, 1)
    async def all_null(system_prompt, user_prompt="", **kw):
        return {"O": None, "C": None, "E": None, "A": None, "N": None}
    monkeypatch.setattr(traits, "chat_json", all_null)
    monkeypatch.setattr(traits, "DIMENSION_MAP", {"ocean": traits.DIMENSION_MAP["ocean"]})
    memory.append_message("user", "a neutral sentence")
    await traits.run(0, 0)
    assert model.get_trait("ocean")["content_json"]["O"]["score"] == 70


@pytest.mark.asyncio
async def test_schwartz_job_persists_signed_evidence_and_projects_all_ten_values(
    migrated_db, monkeypatch,
):
    async def signed_values(system_prompt, user_prompt="", **kw):
        return {
            "self_direction": {
                "direction": "support", "strength": 0.9, "confidence": 0.8,
                "basis": "tradeoff", "evidence": "I chose autonomy",
                "counterpart": "security", "episode": "choosing autonomy",
            },
            "security": {
                "direction": "sacrifice", "strength": 0.8, "confidence": 0.8,
                "basis": "tradeoff", "evidence": "despite the risk",
                "counterpart": "self_direction", "episode": "choosing autonomy",
            },
            "achievement": None, "power": None, "hedonism": None,
            "stimulation": None, "universalism": None, "benevolence": None,
            "tradition": None, "conformity": None,
        }

    monkeypatch.setattr(traits, "chat_json", signed_values)
    monkeypatch.setattr(
        traits, "DIMENSION_MAP", {"schwartz": traits.DIMENSION_MAP["schwartz"]},
    )
    memory.append_message("user", "I chose autonomy despite the risk")

    await traits.run(0, 0)

    current = model.get_trait("schwartz")["content_json"]
    assert list(current) == [
        "self_direction", "stimulation", "hedonism", "achievement", "power",
        "security", "conformity", "tradition", "benevolence", "universalism",
    ]
    assert current["self_direction"]["priority"] > 0
    assert current["security"]["priority"] < 0
    assert current["security"]["stance"] == "yielding"
    assert current["tradition"]["status"] == "unobserved"
    evidence = model.get_trait_evidence("schwartz")
    assert [(e["subdimension"], e["direction"]) for e in evidence] == [
        ("self_direction", "support"), ("security", "sacrifice"),
    ]


@pytest.mark.asyncio
async def test_schwartz_job_rejects_stale_v1_output_without_touching_v2_state(
    migrated_db, monkeypatch,
):
    row = {
        "dimension": "schwartz",
        "subdimension": "self_direction",
        "episode_key": "episode:existing:self_direction",
        "direction": "support",
        "strength": 0.8,
        "confidence": 0.8,
        "basis": "tradeoff",
        "episode": "existing choice",
        "evidence": "existing evidence",
    }
    model.add_trait_evidence([row])
    model.set_trait(
        "schwartz",
        traits.schwartz.project(model.get_trait_evidence("schwartz")),
        sample_count=4,
    )
    old_current = model.get_trait("schwartz")
    old_history = model.get_trait_history("schwartz")
    old_evidence = model.get_trait_evidence("schwartz")

    async def stale_scores(system_prompt, user_prompt="", **kw):
        output = {key: None for key in traits.schwartz.VALUE_KEYS}
        output["achievement"] = {
            "score": 78, "confidence": 0.8, "evidence": "legacy output",
        }
        return output

    monkeypatch.setattr(traits, "chat_json", stale_scores)
    monkeypatch.setattr(
        traits, "DIMENSION_MAP", {"schwartz": traits.DIMENSION_MAP["schwartz"]},
    )
    memory.append_message("user", "a new choice")

    await traits.run(0, 0)

    assert model.get_trait("schwartz") == old_current
    assert model.get_trait_history("schwartz") == old_history
    assert model.get_trait_evidence("schwartz") == old_evidence
