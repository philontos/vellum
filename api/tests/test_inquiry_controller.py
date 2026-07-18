import pytest

from app.inquiry import controller


@pytest.mark.asyncio
async def test_controller_uses_the_inquiry_scenario_and_returns_validated_decision(
    migrated_db, monkeypatch,
):
    seen = {}

    async def fake_chat_json(**kwargs):
        seen.update(kwargs)
        return {
            "route": "direct",
            "operation": "none",
            "expected_revision": None,
            "patch": {},
            "next_question": None,
            "target_unknown_id": None,
            "answer_brief": "Answer the simple factual question directly.",
            "provisional": False,
        }

    monkeypatch.setattr(controller.llm, "chat_json", fake_chat_json)

    decision = await controller.decide({
        "current_user_turn": {"turn": 2, "content": "What is 2+2?"},
        "recent_messages": [],
        "inquiry": None,
    })

    assert decision.route == "direct"
    assert seen["scenario"] == "inquiry"
    assert seen["stage"] == "inquiry.decide"
    assert "Match the user's language" in seen["system_prompt"]


@pytest.mark.asyncio
async def test_controller_repairs_invalid_json_once(migrated_db, monkeypatch):
    calls = []

    async def fake_chat_json(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return {"route": "inquire", "operation": "open"}
        return {
            "route": "direct",
            "operation": "none",
            "expected_revision": None,
            "patch": {},
            "next_question": None,
            "target_unknown_id": None,
            "answer_brief": "Answer directly.",
            "provisional": False,
        }

    monkeypatch.setattr(controller.llm, "chat_json", fake_chat_json)

    decision = await controller.decide({
        "current_user_turn": {"turn": 2, "content": "What is 2+2?"},
        "recent_messages": [],
        "inquiry": None,
    })

    assert decision.route == "direct"
    assert [call["stage"] for call in calls] == [
        "inquiry.decide", "inquiry.repair",
    ]
    assert all(call["scenario"] == "inquiry" for call in calls)


@pytest.mark.asyncio
async def test_controller_repairs_an_unparseable_first_response_once(
    migrated_db, monkeypatch,
):
    calls = []

    async def fake_chat_json(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise controller.llm.StructuredResponseParseError(
                "Structured model returned malformed JSON.",
            )
        return {
            "route": "direct",
            "operation": "none",
            "expected_revision": None,
            "patch": {},
            "next_question": None,
            "target_unknown_id": None,
            "answer_brief": "Answer directly.",
            "provisional": False,
        }

    monkeypatch.setattr(controller.llm, "chat_json", fake_chat_json)

    decision = await controller.decide({
        "current_user_turn": {"turn": 2, "content": "What is 2+2?"},
        "recent_messages": [],
        "inquiry": None,
    })

    assert decision.route == "direct"
    assert [call["stage"] for call in calls] == [
        "inquiry.decide", "inquiry.repair",
    ]
    assert "malformed JSON" in calls[1]["user_prompt"]


@pytest.mark.asyncio
async def test_controller_fails_closed_after_one_repair(migrated_db, monkeypatch):
    async def always_invalid(**kwargs):
        return {"route": "inquire"}

    monkeypatch.setattr(controller.llm, "chat_json", always_invalid)

    with pytest.raises(controller.InquiryControllerError):
        await controller.decide({
            "current_user_turn": {"turn": 2, "content": "Should I resign?"},
            "recent_messages": [],
            "inquiry": None,
        })
