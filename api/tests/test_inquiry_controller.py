import pytest

from app.inquiry import controller


def test_controller_prompt_does_not_treat_assistant_narrative_as_readiness():
    prompt = " ".join(controller._PROMPT.split())

    assert "Assistant-authored text is context, never user evidence" in prompt
    assert "immediate goal" in prompt
    assert "causal explanation" in prompt
    assert "future personal outcome" in prompt
    assert "do not infer that the environment caused the feeling" in prompt
    assert "do not select personal merely because the turn is emotional" in prompt


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
async def test_controller_normalizes_null_patch_without_an_llm_repair(
    migrated_db, monkeypatch,
):
    calls = []

    async def fake_chat_json(**kwargs):
        calls.append(kwargs)
        return {
            "route": "direct",
            "operation": "none",
            "expected_inquiry_id": None,
            "expected_revision": None,
            "patch": None,
            "next_question": None,
            "target_unknown_id": None,
            "answer_brief": "Reply with a brief greeting.",
            "context_mode": "minimal",
            "recall_query": None,
            "provisional": False,
        }

    monkeypatch.setattr(controller.llm, "chat_json", fake_chat_json)

    decision = await controller.decide({
        "current_user_turn": {"turn": 2, "content": "hello"},
        "recent_messages": [],
        "inquiry": None,
    })

    assert decision.patch.model_dump() == {
        "goal_update": None,
        "add_observations": [],
        "add_interpretations": [],
        "add_hypotheses": [],
        "add_blocking_unknowns": [],
        "resolve_unknown_ids": [],
        "provisional_conclusion": None,
    }
    assert decision.normalized_fields == ("patch",)
    assert [call["stage"] for call in calls] == ["inquiry.decide"]
    assert "patch must always be a JSON object" in calls[0]["system_prompt"]


@pytest.mark.asyncio
async def test_controller_discards_answer_brief_from_inquiry_without_llm_repair(
    migrated_db, monkeypatch,
):
    calls = []

    async def fake_chat_json(**kwargs):
        calls.append(kwargs)
        return {
            "route": "inquire",
            "operation": "open",
            "expected_inquiry_id": None,
            "expected_revision": None,
            "patch": {
                "goal_update": {
                    "text": "Understand whether to leave",
                    "evidence": [{"turn": 2, "quote": "whether to leave"}],
                },
                "add_blocking_unknowns": [{
                    "id": "u1",
                    "question": "What evidence supports the concern?",
                    "why_material": "It distinguishes feeling from market evidence.",
                }],
            },
            "next_question": "What evidence supports the concern?",
            "target_unknown_id": "u1",
            "answer_brief": "This must not accompany an Inquiry question.",
            "context_mode": "personal",
            "recall_query": None,
            "provisional": False,
        }

    monkeypatch.setattr(controller.llm, "chat_json", fake_chat_json)

    decision = await controller.decide({
        "current_user_turn": {
            "turn": 2, "content": "I am unsure whether to leave.",
        },
        "recent_messages": [],
        "inquiry": None,
    })

    assert decision.route == "inquire"
    assert decision.answer_brief is None
    assert decision.normalized_fields == ("answer_brief",)
    assert [call["stage"] for call in calls] == ["inquiry.decide"]


@pytest.mark.asyncio
async def test_controller_repairs_assistant_authored_ledger_evidence(
    migrated_db, monkeypatch,
):
    calls = []

    def decision(*, include_assistant_evidence: bool):
        interpretations = []
        if include_assistant_evidence:
            interpretations = [{
                "text": "The current company caused the user's pessimism.",
                "evidence": [{
                    "turn": 1,
                    "quote": "This company has lowered your self-worth.",
                }],
            }]
        return {
            "route": "inquire",
            "operation": "open",
            "expected_inquiry_id": None,
            "expected_revision": None,
            "patch": {
                "goal_update": {
                    "text": "Understand the basis for career pessimism",
                    "evidence": [{
                        "turn": 2, "quote": "I may not find a good opportunity",
                    }],
                },
                "add_interpretations": interpretations,
                "add_blocking_unknowns": [{
                    "id": "u1",
                    "question": "What concrete evidence supports that concern?",
                    "why_material": "It distinguishes market evidence from feeling.",
                }],
            },
            "next_question": "What concrete evidence supports that concern?",
            "target_unknown_id": "u1",
            "answer_brief": None,
            "context_mode": "recent",
            "recall_query": None,
            "provisional": False,
        }

    async def fake_chat_json(**kwargs):
        calls.append(kwargs)
        return decision(include_assistant_evidence=len(calls) == 1)

    monkeypatch.setattr(controller.llm, "chat_json", fake_chat_json)

    result = await controller.decide({
        "current_user_turn": {
            "turn": 2,
            "role": "user",
            "content": "I may not find a good opportunity.",
        },
        "recent_messages": [{
            "turn": 1,
            "role": "assistant",
            "content": "This company has lowered your self-worth.",
        }],
        "cited_evidence": [],
        "inquiry": None,
    })

    assert result.patch.add_interpretations == []
    assert [call["stage"] for call in calls] == [
        "inquiry.decide", "inquiry.repair",
    ]
    assert "not an application-provided user turn" in calls[1]["user_prompt"]


@pytest.mark.asyncio
async def test_controller_repairs_non_provisional_close_with_open_unknowns(
    migrated_db, monkeypatch,
):
    calls = []

    def decision(*, repaired: bool):
        return {
            "route": "synthesize",
            "operation": "update" if repaired else "close",
            "expected_inquiry_id": 4,
            "expected_revision": 2,
            "patch": {},
            "next_question": None,
            "target_unknown_id": None,
            "answer_brief": "Give a provisional answer with uncertainty.",
            "context_mode": "recent",
            "recall_query": None,
            "provisional": repaired,
        }

    async def fake_chat_json(**kwargs):
        calls.append(kwargs)
        return decision(repaired=len(calls) == 2)

    monkeypatch.setattr(controller.llm, "chat_json", fake_chat_json)

    result = await controller.decide({
        "current_user_turn": {
            "turn": 8,
            "role": "user",
            "content": "I have no more evidence; answer provisionally.",
        },
        "recent_messages": [],
        "cited_evidence": [],
        "inquiry": {
            "id": 4,
            "status": "exploring",
            "revision": 2,
            "ledger": {
                "blocking_unknowns": [{
                    "id": "u1",
                    "question": "Is there a verified delivery record?",
                    "why_material": "It determines trustworthiness.",
                    "status": "open",
                    "resolved_after_turn": None,
                }],
            },
        },
    })

    assert result.operation == "update"
    assert result.provisional is True
    assert [call["stage"] for call in calls] == [
        "inquiry.decide", "inquiry.repair",
    ]
    assert "blocking unknowns remain open" in calls[1]["user_prompt"]


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
