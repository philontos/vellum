"""Controller-result checks that must pass before durable Inquiry state."""

from app.inquiry import readiness
from app.inquiry.contracts import InquiryDecision


class InquiryEvidenceError(ValueError):
    pass


class InquiryReadinessError(ValueError):
    pass


def _user_turns(context: dict) -> dict[int, str]:
    turns: dict[int, str] = {}
    current = context.get("current_user_turn")
    if isinstance(current, dict):
        turn = current.get("turn")
        content = current.get("content")
        if isinstance(turn, int) and isinstance(content, str):
            turns[turn] = content
    for key in ("recent_messages", "cited_evidence"):
        for message in context.get(key) or []:
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            turn = message.get("turn")
            content = message.get("content")
            if isinstance(turn, int) and isinstance(content, str):
                turns[turn] = content
    return turns


def _evidence_refs(decision: InquiryDecision):
    patch = decision.patch
    if patch.goal_update is not None:
        yield from patch.goal_update.evidence
    for item in (*patch.add_observations, *patch.add_interpretations):
        yield from item.evidence
    for item in patch.add_hypotheses:
        yield from item.supporting_evidence
        yield from item.disconfirming_evidence
    for item in decision.user_state.states:
        yield from item.evidence
    for item in decision.user_state.deltas:
        yield from item.evidence
    yield from decision.synthesis_basis_evidence


def _validate_evidence(decision: InquiryDecision, context: dict) -> None:
    user_turns = _user_turns(context)
    for ref in _evidence_refs(decision):
        content = user_turns.get(ref.turn)
        if content is None:
            raise InquiryEvidenceError(
                f"Evidence turn {ref.turn} is not an application-provided user turn"
            )
        if ref.quote not in content:
            raise InquiryEvidenceError(
                f"Evidence quote is not present in user turn {ref.turn}"
            )
    if decision.synthesis_basis in {
        "user_requested_provisional", "user_cannot_add_evidence",
    }:
        current_turn = (context.get("current_user_turn") or {}).get("turn")
        if any(
            ref.turn != current_turn
            for ref in decision.synthesis_basis_evidence
        ):
            raise InquiryEvidenceError(
                "a user-driven provisional synthesis basis must cite the current turn"
            )


def _validate_readiness(decision: InquiryDecision, context: dict) -> None:
    try:
        readiness.validate_open(decision)
    except readiness.ReadinessGap as error:
        raise InquiryReadinessError(str(error)) from error
    inquiry = context.get("inquiry")
    if isinstance(inquiry, dict) and decision.expected_inquiry_id == inquiry.get("id"):
        try:
            readiness.validate_frame_transition(
                inquiry.get("ledger") or {}, decision,
            )
        except readiness.ReadinessGap as error:
            raise InquiryReadinessError(str(error)) from error
    if decision.route != "synthesize":
        return
    if not isinstance(inquiry, dict):
        return
    if decision.operation == "none" and inquiry.get("status") in {
        "exploring", "reviewing",
    }:
        raise InquiryReadinessError(
            "An active Inquiry synthesis must advance its revision"
        )
    if decision.expected_inquiry_id != inquiry.get("id"):
        return
    ledger = inquiry.get("ledger") or {}
    open_ids = {
        item.get("id")
        for item in ledger.get("blocking_unknowns") or []
        if item.get("status") == "open"
    }
    open_ids.difference_update(decision.patch.resolve_unknown_ids)
    open_ids.update(item.id for item in decision.patch.add_blocking_unknowns)
    if open_ids:
        if decision.operation == "close":
            raise InquiryReadinessError(
                "blocking unknowns remain open; update or pause instead of closing"
            )
        if not decision.provisional:
            raise InquiryReadinessError(
                "blocking unknowns remain open; synthesis must be provisional"
            )
    try:
        readiness.validate(ledger, decision)
    except readiness.ReadinessGap as error:
        raise InquiryReadinessError(str(error)) from error


def validate(decision: InquiryDecision, context: dict) -> None:
    _validate_evidence(decision, context)
    _validate_readiness(decision, context)
