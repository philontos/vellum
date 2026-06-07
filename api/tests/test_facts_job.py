import pytest

from app.model_loop import facts
from app.store import memory, model


@pytest.mark.asyncio
async def test_facts_extracted_and_deduped(migrated_db, monkeypatch):
    calls = {"n": 0}

    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        calls["n"] += 1
        return {"facts": ["allergic to penicillin", "lives in Beijing"]}
    monkeypatch.setattr(facts, "chat_json", fake_chat_json)

    memory.append_message("user", "btw I'm allergic to penicillin and live in Beijing")
    await facts.run(start_turn=0, end_turn=0)
    assert sorted(f["text"] for f in model.active_facts()) == ["allergic to penicillin", "lives in Beijing"]

    # second run over the same content must not duplicate
    await facts.run(start_turn=0, end_turn=0)
    assert len(model.active_facts()) == 2
