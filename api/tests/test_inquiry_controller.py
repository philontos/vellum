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
async def test_controller_repairs_branch_answer_that_closes_before_concrete_experience(
    migrated_db, monkeypatch,
):
    calls = []

    def proposed(*, repaired: bool):
        patch = {
            "resolve_unknown_ids": ["u1"],
        }
        if repaired:
            patch["add_blocking_unknowns"] = [{
                "id": "u2",
                "kind": "concrete_experience",
                "question": "What happened recently that deepened the disappointment?",
                "why_material": "A concrete change is needed before interpreting it.",
            }]
        return {
            "route": "inquire" if repaired else "synthesize",
            "operation": "update" if repaired else "close",
            "expected_inquiry_id": 1,
            "expected_revision": 1,
            "patch": patch,
            "user_state": {
                "states": [{
                    "dimension": "emotion",
                    "text": "The user is disappointed with the current company.",
                    "evidence": [{
                        "turn": 268,
                        "quote": "主要是对当前公司的失望",
                    }],
                }],
                "deltas": [],
            },
            "next_question": (
                "What happened recently that deepened the disappointment?"
                if repaired else None
            ),
            "target_unknown_id": "u2" if repaired else None,
            "answer_brief": None if repaired else (
                "Explain why watching outside opportunities is correct."
            ),
            "context_mode": "recent",
            "recall_query": None,
            "provisional": False,
            "synthesis_basis": None if repaired else "ready",
            "synthesis_basis_evidence": [],
        }

    async def fake_chat_json(**kwargs):
        calls.append(kwargs)
        return proposed(repaired=len(calls) == 2)

    monkeypatch.setattr(controller.llm, "chat_json", fake_chat_json)

    result = await controller.decide({
        "current_user_turn": {
            "turn": 268,
            "role": "user",
            "content": "主要是对当前公司的失望",
        },
        "recent_messages": [{
            "turn": 266,
            "role": "user",
            "content": "我是不是应该保持对外界机会的关注？感觉对公司越来越没信心",
        }],
        "assistant_context": [{
            "turn": 267,
            "role": "assistant",
            "content": "是外部机会更好，还是主要对内部失望？",
        }],
        "cited_evidence": [],
        "inquiry": {
            "id": 1,
            "status": "exploring",
            "revision": 1,
            "ledger": {
                "frame": {
                    "mode": "personal",
                    "answer_scope": "bounded_guidance",
                    "state_delta_required": True,
                },
                "goal": {
                    "text": "Decide whether to keep watching outside opportunities.",
                    "evidence": [{
                        "turn": 266,
                        "quote": "我是不是应该保持对外界机会的关注？",
                    }],
                },
                "current_state": [{
                    "dimension": "belief",
                    "text": "The user is losing confidence in the company.",
                    "evidence": [{
                        "turn": 266,
                        "quote": "感觉对公司越来越没信心",
                    }],
                }],
                "state_deltas": [{
                    "dimension": "belief",
                    "text": "Confidence in the company is declining.",
                    "reference": "unspecified_past",
                    "evidence": [{
                        "turn": 266,
                        "quote": "越来越没信心",
                    }],
                }],
                "observations": [],
                "interpretations": [],
                "hypotheses": [],
                "blocking_unknowns": [{
                    "id": "u1",
                    "kind": "orientation",
                    "question": "Is the doubt external or internal?",
                    "why_material": "It locates the concern.",
                    "status": "open",
                    "resolved_after_turn": None,
                }],
                "asked_questions": [],
                "provisional_conclusion": None,
            },
        },
    })

    assert result.route == "inquire"
    assert result.operation == "update"
    assert result.target_unknown_id == "u2"
    assert result.patch.add_blocking_unknowns[0].kind == "concrete_experience"
    assert [call["stage"] for call in calls] == [
        "inquiry.decide", "inquiry.repair",
    ]
    assert "concrete experience" in calls[1]["user_prompt"]


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
        "frame_update": None,
        "add_observations": [],
        "add_interpretations": [],
        "add_hypotheses": [],
        "add_blocking_unknowns": [],
        "resolve_unknown_ids": [],
        "provisional_conclusion": None,
    }
    assert decision.normalized_fields == ("patch", "user_state")
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
                "frame_update": {
                    "mode": "personal",
                    "answer_scope": "consequential_decision",
                    "state_delta_required": False,
                },
                "goal_update": {
                    "text": "Understand whether to leave",
                    "evidence": [{"turn": 2, "quote": "whether to leave"}],
                },
                "add_blocking_unknowns": [{
                    "id": "u1",
                    "kind": "concrete_experience",
                    "question": "What evidence supports the concern?",
                    "why_material": "It distinguishes feeling from market evidence.",
                }],
            },
            "user_state": {
                "states": [{
                    "dimension": "intention",
                    "text": "The user is considering whether to leave.",
                    "evidence": [{"turn": 2, "quote": "whether to leave"}],
                }],
                "deltas": [],
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
                "frame_update": {
                    "mode": "personal",
                    "answer_scope": "causal_judgment",
                    "state_delta_required": False,
                },
                "goal_update": {
                    "text": "Understand the basis for career pessimism",
                    "evidence": [{
                        "turn": 2, "quote": "I may not find a good opportunity",
                    }],
                },
                "add_interpretations": interpretations,
                "add_blocking_unknowns": [{
                    "id": "u1",
                    "kind": "concrete_experience",
                    "question": "What concrete evidence supports that concern?",
                    "why_material": "It distinguishes market evidence from feeling.",
                }],
            },
            "user_state": {
                "states": [{
                    "dimension": "belief",
                    "text": "The user doubts that a good opportunity exists.",
                    "evidence": [{
                        "turn": 2, "quote": "I may not find a good opportunity",
                    }],
                }],
                "deltas": [],
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
            "synthesis_basis": (
                "user_requested_provisional" if repaired else "ready"
            ),
            "synthesis_basis_evidence": ([{
                "turn": 8,
                "quote": "I have no more evidence; answer provisionally",
            }] if repaired else []),
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
