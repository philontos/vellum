import pytest

from app.inquiry.contracts import InquiryDecision
from evals import inquiry, suites


def _decision(route: str) -> InquiryDecision:
    values = {
        "route": route,
        "operation": "none",
        "expected_revision": None,
        "patch": {},
        "next_question": None,
        "target_unknown_id": None,
        "answer_brief": "Answer it.",
        "provisional": False,
    }
    if route == "inquire":
        values.update({
            "operation": "open",
            "patch": {
                "goal_update": {
                    "text": "Decide whether to resign",
                    "evidence": [{"turn": 10, "quote": "Should I resign?"}],
                },
                "add_blocking_unknowns": [{
                    "id": "u1", "question": "What happened?",
                    "why_material": "The event changes the judgment.",
                }],
            },
            "next_question": "What happened?",
            "target_unknown_id": "u1",
            "answer_brief": None,
        })
    return InquiryDecision.model_validate(values)


def test_cases_cover_direct_inquire_and_synthesize_routes():
    cases = inquiry.load_cases()
    expected = {case["expected_route"] for case in cases}

    assert expected == {"direct", "inquire", "synthesize"}


def test_simple_direct_cases_require_minimal_responder_context():
    cases = {case["id"]: case for case in inquiry.load_cases()}

    assert cases["direct_factual"]["expected_context_mode"] == "minimal"
    assert cases["direct_writing"]["expected_context_mode"] == "minimal"


def test_cases_cover_ambiguous_career_doubt_after_assistant_certainty():
    case = {
        item["id"]: item for item in inquiry.load_cases()
    }["inquire_career_pessimism_after_assistant_narrative"]

    assert case["expected_route"] == "inquire"
    assert case["allowed_operations"] == ["open"]
    assert any(
        message["role"] == "assistant" and "下一份" in message["content"]
        for message in case["messages"]
    )
    assert case["messages"][-1]["role"] == "user"


def test_cases_preserve_direct_route_when_user_explicitly_requests_presence_only():
    case = {
        item["id"]: item for item in inquiry.load_cases()
    }["direct_explicit_emotional_presence"]

    assert case["expected_route"] == "direct"
    assert set(case["allowed_context_modes"]) == {"minimal", "recent"}


def test_inquiry_suite_reports_context_mode_accuracy():
    aggregate = suites.SUITES["inquiry"].aggregate([
        {"passed": True, "context_mode_ok": True},
        {"passed": False, "context_mode_ok": False},
    ])

    assert aggregate["context_mode_accuracy"] == 0.5


def test_eval_context_matches_production_question_policy_without_current_duplication():
    case = {
        "messages": [
            {"turn": 10, "role": "user", "content": "Should I resign?"},
            {"turn": 11, "role": "assistant", "content": "What happened?"},
            {"turn": 12, "role": "user", "content": "It happened again."},
        ],
        "inquiry": {
            "ledger": {
                "asked_questions": [
                    {"unknown_id": "u1", "text": "What happened?"},
                ],
            },
        },
    }

    context = inquiry._context(case)

    assert context["current_user_turn"]["turn"] == 12
    assert [message["turn"] for message in context["recent_messages"]] == [10, 11]
    assert context["policy"] == {
        "max_questions": 5,
        "questions_asked": 1,
        "remaining_questions": 4,
    }


@pytest.mark.asyncio
async def test_inquiry_eval_scores_routing_and_exact_user_evidence(monkeypatch):
    case = {
        "id": "resign",
        "messages": [{"turn": 10, "role": "user", "content": "Should I resign?"}],
        "expected_route": "inquire",
        "allowed_operations": ["open"],
    }
    monkeypatch.setattr(inquiry.controller, "decide", lambda ctx: _async(
        _decision("inquire"),
    ))

    result = await inquiry.run_case(case)

    assert result["passed"] is True
    assert result["route_ok"] is True
    assert result["evidence_valid"] is True
    assert result["one_question"] is True


@pytest.mark.asyncio
async def test_inquiry_eval_accepts_grounded_refinement_of_expected_unknown(
    monkeypatch,
):
    case = {
        "id": "refine-event",
        "messages": [
            {"turn": 10, "role": "user", "content": "Should I resign?"},
            {"turn": 11, "role": "assistant", "content": "What happened?"},
            {
                "turn": 12,
                "role": "user",
                "content": "My manager dismisses me in meetings.",
            },
        ],
        "inquiry": {
            "id": 1,
            "status": "exploring",
            "revision": 1,
            "ledger": {
                "goal": {
                    "text": "Decide whether to resign",
                    "evidence": [{"turn": 10, "quote": "Should I resign?"}],
                },
                "observations": [],
                "interpretations": [],
                "hypotheses": [],
                "blocking_unknowns": [{
                    "id": "u1",
                    "question": "What happened?",
                    "why_material": "A concrete event changes the judgment.",
                    "status": "open",
                    "resolved_after_turn": None,
                }],
                "asked_questions": [{
                    "unknown_id": "u1",
                    "text": "What happened?",
                    "after_turn": 10,
                }],
                "provisional_conclusion": None,
            },
        },
        "expected_route": "inquire",
        "allowed_operations": ["update"],
        "expected_target_unknown_id": "u1",
    }
    refined = InquiryDecision.model_validate({
        "route": "inquire",
        "operation": "update",
        "expected_inquiry_id": 1,
        "expected_revision": 1,
        "patch": {
            "add_observations": [{
                "text": "The manager dismisses the user in meetings.",
                "evidence": [{
                    "turn": 12,
                    "quote": "My manager dismisses me in meetings.",
                }],
            }],
            "resolve_unknown_ids": ["u1"],
            "add_blocking_unknowns": [{
                "id": "u2",
                "question": "What was said in one recent meeting?",
                "why_material": "A concrete exchange distinguishes explanations.",
            }],
        },
        "next_question": "What was said in one recent meeting?",
        "target_unknown_id": "u2",
        "answer_brief": None,
        "context_mode": "recent",
        "recall_query": None,
        "provisional": False,
    })
    monkeypatch.setattr(
        inquiry.controller, "decide", lambda ctx: _async(refined),
    )

    result = await inquiry.run_case(case)

    assert result["target_ok"] is True
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_inquiry_eval_flags_premature_answer(monkeypatch):
    case = {
        "id": "resign",
        "messages": [{"turn": 10, "role": "user", "content": "Should I resign?"}],
        "expected_route": "inquire",
    }
    monkeypatch.setattr(inquiry.controller, "decide", lambda ctx: _async(
        _decision("direct"),
    ))

    result = await inquiry.run_case(case)

    assert result["passed"] is False
    assert result["premature_answer"] is True


@pytest.mark.asyncio
async def test_inquiry_eval_flags_unnecessarily_heavy_responder_context(monkeypatch):
    case = {
        "id": "simple-fact",
        "messages": [{"turn": 10, "role": "user", "content": "法国首都？"}],
        "expected_route": "direct",
        "expected_context_mode": "minimal",
    }
    decision = _decision("direct")
    monkeypatch.setattr(inquiry.controller, "decide", lambda ctx: _async(decision))

    result = await inquiry.run_case(case)

    assert result["actual_context_mode"] == "personal"
    assert result["context_mode_ok"] is False
    assert result["passed"] is False


@pytest.mark.asyncio
async def test_inquiry_eval_accepts_any_explicitly_allowed_context_mode(monkeypatch):
    case = {
        "id": "presence",
        "messages": [{
            "turn": 10,
            "role": "user",
            "content": "Please just stay with me; no analysis today.",
        }],
        "expected_route": "direct",
        "allowed_context_modes": ["minimal", "recent"],
    }
    decision = _decision("direct")
    decision.context_mode = "minimal"
    monkeypatch.setattr(
        inquiry.controller, "decide", lambda ctx: _async(decision),
    )

    result = await inquiry.run_case(case)

    assert result["context_mode_ok"] is True
    assert result["passed"] is True


@pytest.mark.asyncio
async def test_inquiry_eval_flags_a_wrong_optimistic_lock(monkeypatch):
    case = {
        "id": "wrong-lock",
        "messages": [{"turn": 10, "role": "user", "content": "Answer now."}],
        "inquiry": {
            "id": 7, "status": "exploring", "revision": 3,
            "ledger": {
                "goal": None, "observations": [], "interpretations": [],
                "hypotheses": [], "blocking_unknowns": [],
                "asked_questions": [], "provisional_conclusion": None,
            },
        },
        "expected_route": "synthesize",
        "allowed_operations": ["update"],
    }
    wrong_lock = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "update",
        "expected_inquiry_id": 8, "expected_revision": 3,
        "patch": {}, "next_question": None, "target_unknown_id": None,
        "answer_brief": "Answer.", "provisional": False,
    })
    monkeypatch.setattr(
        inquiry.controller, "decide", lambda ctx: _async(wrong_lock),
    )

    result = await inquiry.run_case(case)

    assert result["route_ok"] is True
    assert result["lock_valid"] is False
    assert result["passed"] is False


def test_inquiry_eval_accepts_an_exact_lock_for_an_older_paused_topic():
    context = {
        "inquiry": {"id": 9, "revision": 2, "status": "paused"},
        "paused_inquiries": [{"id": 7, "revision": 4}],
    }
    decision = {
        "route": "synthesize", "operation": "resume",
        "expected_inquiry_id": 7, "expected_revision": 4,
    }

    assert inquiry._lock_valid(decision, context) is True


async def _async(value):
    return value
