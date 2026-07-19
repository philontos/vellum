from app.chat.context_plan import effective_mode
from app.inquiry.contracts import InquiryDecision


def _direct(mode: str = "personal") -> InquiryDecision:
    return InquiryDecision.model_validate({
        "route": "direct",
        "operation": "none",
        "patch": {},
        "answer_brief": "Reply directly.",
        "context_mode": mode,
        "provisional": False,
    })


def test_low_information_greeting_is_forced_to_minimal_context():
    assert effective_mode(_direct("personal"), "hello") == "minimal"
    assert effective_mode(_direct("personal"), "你好！") == "minimal"


def test_substantive_personal_question_keeps_controller_context_choice():
    assert effective_mode(
        _direct("personal"), "Should I remain a TL or return to an IC role?",
    ) == "personal"


def test_synthesis_uses_grounded_context_because_the_ledger_is_authoritative():
    decision = InquiryDecision.model_validate({
        "route": "synthesize",
        "operation": "update",
        "expected_inquiry_id": 3,
        "expected_revision": 2,
        "patch": {},
        "answer_brief": "Synthesize the grounded Ledger.",
        "context_mode": "personal",
        "provisional": False,
        "synthesis_basis": "ready",
    })

    assert effective_mode(decision, "I am ready for the answer") == "grounded"
