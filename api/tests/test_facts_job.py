import pytest

from app.model_loop import facts


@pytest.mark.asyncio
async def test_extract_facts_cleans_the_list(monkeypatch):
    """extract_facts is the pure perception step (the eval calls it directly):
    span -> list of trimmed, non-empty string facts."""
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        assert kw.get("stage") == "facts"
        return {"facts": ["  allergic to penicillin  ", "", "   ", 123, "lives in Beijing"]}
    monkeypatch.setattr(facts, "chat_json", fake_chat_json)

    out = await facts.extract_facts("some conversation span")
    assert out == ["allergic to penicillin", "lives in Beijing"]
