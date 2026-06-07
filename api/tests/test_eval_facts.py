import pytest

from evals import facts as ef
from app.store import memory


def test_fact_recall_matcher():
    actual = ["allergic to penicillin", "has a sister named Lin in Shanghai"]
    expect = ["allergic to penicillin", "sister", "Shanghai", "vegetarian"]
    score = ef.fact_recall(expect, actual)
    assert score["recall"] == 0.75            # 3 of 4 matched by containment


@pytest.mark.asyncio
async def test_run_case_uses_real_facts_job(migrated_db, monkeypatch):
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        return {"facts": ["allergic to penicillin", "has a sister Lin in Shanghai"]}
    monkeypatch.setattr(ef.facts_job, "chat_json", fake_chat_json)
    case = {"conversation": ["I'm allergic to penicillin; sister Lin in Shanghai"],
            "expect_facts": ["penicillin", "Shanghai"]}
    result = await ef.run_case(case)
    assert result["recall"] == 1.0
