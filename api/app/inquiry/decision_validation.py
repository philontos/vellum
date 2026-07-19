"""Controller-result checks that must pass before durable Inquiry state."""

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


def _validate_readiness(decision: InquiryDecision, context: dict) -> None:
    if decision.route != "synthesize":
        return
    inquiry = context.get("inquiry")
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
    if not open_ids:
        return
    if decision.operation == "close":
        raise InquiryReadinessError(
            "blocking unknowns remain open; update or pause instead of closing"
        )
    if not decision.provisional:
        raise InquiryReadinessError(
            "blocking unknowns remain open; synthesis must be provisional"
        )


def validate(decision: InquiryDecision, context: dict) -> None:
    _validate_evidence(decision, context)
    _validate_readiness(decision, context)
