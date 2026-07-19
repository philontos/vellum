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
            "frame_update": {
                "mode": "practical",
                "answer_scope": "bounded_guidance",
                "state_delta_required": False,
            },
            "goal_update": {
                "text": "Decide whether to resign",
                "evidence": [{"turn": 4, "quote": "Should I resign?"}],
            },
            "add_blocking_unknowns": [{
                "id": "u1",
                "kind": "concrete_experience",
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


def test_consultation_contract_models_scope_current_state_and_change():
    payload = _decision()
    payload["patch"]["frame_update"] = {
        "mode": "personal",
        "answer_scope": "bounded_guidance",
        "state_delta_required": True,
    }
    payload["patch"]["add_blocking_unknowns"][0]["kind"] = (
        "concrete_experience"
    )
    payload["patch"]["add_observations"] = [{
        "kind": "event",
        "text": "A reorganization removed the user's decision authority.",
        "evidence": [{"turn": 4, "quote": "Should I resign?"}],
    }]
    payload["user_state"] = {
        "states": [{
            "dimension": "belief",
            "text": "The user is losing confidence in the company.",
            "evidence": [{"turn": 4, "quote": "Should I resign?"}],
        }],
        "deltas": [{
            "dimension": "belief",
            "text": "Confidence has declined since the earlier discussion.",
            "reference": "previous_episode",
            "evidence": [{"turn": 4, "quote": "Should I resign?"}],
        }],
    }

    decision = InquiryDecision.model_validate(payload)

    assert decision.patch.frame_update.mode == "personal"
    assert decision.patch.add_observations[0].kind == "event"
    assert decision.patch.add_blocking_unknowns[0].kind == "concrete_experience"
    assert decision.user_state.states[0].dimension == "belief"
    assert decision.user_state.deltas[0].reference == "previous_episode"


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
        synthesis_basis="user_requested_provisional",
        synthesis_basis_evidence=[{
            "turn": 4,
            "quote": "Should I resign?",
        }],
    ))

    assert decision.operation == "resume"


def test_provisional_synthesis_requires_an_auditable_escape_basis():
    with pytest.raises(ValidationError):
        InquiryDecision.model_validate(_decision(
            route="synthesize",
            operation="resume",
            expected_inquiry_id=7,
            expected_revision=3,
            patch={},
            next_question=None,
            target_unknown_id=None,
            answer_brief="Answer before the Inquiry is ready.",
            provisional=True,
        ))


def test_ready_synthesis_cannot_masquerade_as_provisional():
    with pytest.raises(ValidationError):
        InquiryDecision.model_validate(_decision(
            route="synthesize",
            operation="close",
            expected_inquiry_id=7,
            expected_revision=3,
            patch={},
            next_question=None,
            target_unknown_id=None,
            answer_brief="Give the grounded conclusion.",
            provisional=False,
            synthesis_basis="user_requested_provisional",
            synthesis_basis_evidence=[{
                "turn": 4,
                "quote": "Should I resign?",
            }],
        ))


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
        claim = {"text": "An unsupported claim", "evidence": []}
        if field == "add_observations":
            claim["kind"] = "event"
        payload["patch"][field] = [claim]

    with pytest.raises(ValidationError):
        InquiryDecision.model_validate(payload)
