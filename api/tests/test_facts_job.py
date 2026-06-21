"""extract_facts is the pure perception view of the integration brain: it runs
the board-aware integrator against an EMPTY board and returns the resulting
adds. The eval calls it directly to measure recall over a cold start."""
import pytest

from app.model_loop import facts


@pytest.mark.asyncio
async def test_extract_facts_cleans_the_list(monkeypatch):
    """span -> list of trimmed, non-empty string facts (the 'add' list, cleaned)."""
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        assert kw.get("stage") == "facts"
        return {"add": ["  allergic to penicillin  ", "", "   ", 123, "lives in Beijing"],
                "update": [], "retire": []}
    monkeypatch.setattr(facts, "chat_json", fake_chat_json)

    out = await facts.extract_facts("some conversation span")
    assert out == ["allergic to penicillin", "lives in Beijing"]


@pytest.mark.asyncio
async def test_extract_facts_runs_against_empty_board(monkeypatch):
    """Perception is the integrator with nothing to reconcile against: the board it
    feeds in is empty (no existing-fact ids), so everything lands as an add."""
    seen: dict = {}

    async def fake(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        return {"add": ["has a cat"], "update": [], "retire": []}
    monkeypatch.setattr(facts, "chat_json", fake)

    out = await facts.extract_facts("I adopted a cat")
    assert out == ["has a cat"]
    assert "I adopted a cat" in seen["prompt"]   # the span is fed in


@pytest.mark.asyncio
async def test_extract_facts_grounds_prompt_with_asof_date(monkeypatch):
    """Given the span's date, the prompt carries it so the model resolves relative
    time ("今年", "年底") against a real date instead of inventing a year."""
    seen: dict = {}

    async def fake(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        return {"add": [], "update": [], "retire": []}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.extract_facts("用户说今年年底加入了一家初创", as_of_date="2026-06-21")
    assert "2026-06-21" in seen["prompt"]


@pytest.mark.asyncio
async def test_extract_facts_without_asof_does_not_leak_none(monkeypatch):
    """The eval path calls extract_facts(span) with no date: the prompt must not
    carry a stray 'None' from formatting an absent date."""
    seen: dict = {}

    async def fake(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        return {"add": [], "update": [], "retire": []}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.extract_facts("some conversation span")
    assert "None" not in seen["prompt"]
