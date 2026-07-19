import pytest
from pydantic import ValidationError

from app.inquiry.contracts import InquiryDecision


def _decision(**overrides):
    payload = {
        "route": "inquire",
        "operation": "open",
        "expected_inquiry_id": None,
        "expected_revision": None,
        "patch": {
            "goal_update": {
                "text": "Decide whether to resign",
                "evidence": [{"turn": 4, "quote": "Should I resign?"}],
            },
            "add_blocking_unknowns": [{
                "id": "u1",
                "question": "What happened most recently?",
                "why_material": "A concrete event separates targeting from feedback.",
            }],
        },
        "next_question": "What happened most recently?",
        "target_unknown_id": "u1",
        "answer_brief": None,
        "provisional": False,
    }
    payload.update(overrides)
    return payload


def test_inquiry_decision_accepts_one_focused_question():
    decision = InquiryDecision.model_validate(_decision())

    assert decision.route == "inquire"
    assert decision.operation == "open"
    assert decision.next_question == "What happened most recently?"


@pytest.mark.parametrize(
    "change",
    [
        {"next_question": None},
        {"target_unknown_id": None},
        {"operation": "none"},
        {"expected_revision": 2},
    ],
)
def test_inquire_route_rejects_incomplete_or_inconsistent_control(change):
    with pytest.raises(ValidationError):
        InquiryDecision.model_validate(_decision(**change))


def test_update_requires_an_expected_revision():
    with pytest.raises(ValidationError):
        InquiryDecision.model_validate(_decision(operation="update"))


def test_revisioned_operation_requires_the_exact_inquiry_id():
    with pytest.raises(ValidationError):
        InquiryDecision.model_validate(_decision(
            operation="update", expected_revision=2,
        ))


def test_direct_route_cannot_hide_a_ledger_mutation():
    with pytest.raises(ValidationError):
        InquiryDecision.model_validate(_decision(
            route="direct",
            operation="open",
            next_question=None,
            target_unknown_id=None,
        ))


def test_direct_route_can_pause_an_active_inquiry_on_a_topic_switch():
    decision = InquiryDecision.model_validate(_decision(
        route="direct",
        operation="pause",
        expected_inquiry_id=7,
        expected_revision=3,
        patch={},
        next_question=None,
        target_unknown_id=None,
        answer_brief="Answer the new unrelated request directly.",
    ))

    assert decision.operation == "pause"


def test_synthesis_can_resume_a_paused_inquiry_when_new_evidence_is_enough():
    decision = InquiryDecision.model_validate(_decision(
        route="synthesize",
        operation="resume",
        expected_inquiry_id=7,
        expected_revision=3,
        patch={},
        next_question=None,
        target_unknown_id=None,
        answer_brief="Give a provisional synthesis from the updated evidence.",
        provisional=True,
    ))

    assert decision.operation == "resume"


def test_contract_forbids_unknown_fields():
    with pytest.raises(ValidationError):
        InquiryDecision.model_validate({**_decision(), "secret_mode": "guess"})


def test_direct_decision_carries_a_bounded_responder_context_plan():
    decision = InquiryDecision.model_validate(_decision(
        route="direct",
        operation="none",
        patch={},
        next_question=None,
        target_unknown_id=None,
        answer_brief="Answer from the recent exchange only.",
        context_mode="recent",
        recall_query=None,
    ))

    assert decision.context_mode == "recent"
    assert decision.recall_query is None


@pytest.mark.parametrize("field", ["goal_update", "add_observations", "add_interpretations"])
def test_grounded_ledger_claims_require_at_least_one_evidence_quote(field):
    payload = _decision()
    if field == "goal_update":
        payload["patch"][field]["evidence"] = []
    else:
        payload["patch"][field] = [{"text": "An unsupported claim", "evidence": []}]

    with pytest.raises(ValidationError):
        InquiryDecision.model_validate(payload)
