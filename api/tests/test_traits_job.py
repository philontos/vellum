import pytest

from app.model_loop import traits
from app.store import memory, model


@pytest.mark.asyncio
async def test_trait_job_updates_current_and_history(migrated_db, monkeypatch):
    # one strong OCEAN-openness signal for every dimension extract
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
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
