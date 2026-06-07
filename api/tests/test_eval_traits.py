import pytest

from evals import traits as et
from app.store import model


@pytest.mark.asyncio
async def test_direction_scoring_high(migrated_db, monkeypatch):
    # mock extraction: strong O-high signal, others null
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        return {"O": {"score": 88, "confidence": 0.7, "evidence": "x"},
                "C": None, "E": None, "A": None, "N": None}
    monkeypatch.setattr(et.traits_job, "chat_json", fake_chat_json)
    monkeypatch.setattr(et.traits_job, "DIMENSION_MAP",
                        {"ocean": et.traits_job.DIMENSION_MAP["ocean"]})

    case = {"dimension": "ocean", "target": {"sub": "O", "direction": "high"},
            "crosstalk_tolerance": 25,
            "conversation": ["I love unfamiliar experiments", "I chase strange ideas"]}
    result = await et.run_case(case)
    assert result["direction_ok"] is True
    assert result["crosstalk_ok"] is True       # others stayed near prior (no signal)


def test_direction_check_pure():
    assert et.direction_ok("high", 65) is True
    assert et.direction_ok("high", 45) is False
    assert et.direction_ok("low", 30) is True
    assert et.direction_ok("mid", 50) is True
    assert et.direction_ok("mid", 80) is False
