import pytest

from app.model_loop import dossier
from app.store import memory, model


@pytest.mark.asyncio
async def test_dossier_rewritten_from_span_and_prior(migrated_db, monkeypatch):
    seen = {}

    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        return {"dossier": "Values autonomy; tends to over-index on others' approval."}
    monkeypatch.setattr(dossier, "chat_json", fake_chat_json)

    model.set_dossier("Prior: enjoys learning.")
    memory.append_message("user", "I said yes again when I wanted to say no")
    await dossier.run(start_turn=0, end_turn=0)

    assert "autonomy" in model.get_dossier()
    assert "Prior: enjoys learning." in seen["prompt"]   # prior fed in for rewrite


@pytest.mark.asyncio
async def test_dossier_missing_key_is_noop(migrated_db, monkeypatch):
    model.set_dossier("original portrait")
    async def empty(system_prompt, user_prompt="", **kw): return {}
    monkeypatch.setattr(dossier, "chat_json", empty)
    memory.append_message("user", "x")
    await dossier.run(0, 0)
    assert model.get_dossier() == "original portrait"
