import pytest

from evals import judge


@pytest.mark.asyncio
async def test_judge_parses_score(monkeypatch):
    async def fake_eval_chat(prompt):
        return '{"score": 8, "reason": "captures autonomy + fear of failure"}'
    monkeypatch.setattr(judge, "_eval_chat", fake_eval_chat)
    out = await judge.score("rubric...", "subject...")
    assert out["score"] == 8


@pytest.mark.asyncio
async def test_judge_handles_fenced_json(monkeypatch):
    async def fake_eval_chat(prompt):
        return "```json\n{\"score\": 3}\n```"
    monkeypatch.setattr(judge, "_eval_chat", fake_eval_chat)
    out = await judge.score("r", "s")
    assert out["score"] == 3
