"""Evidence coverage required before a consultative Inquiry may synthesize."""

from app import config
from app.inquiry.contracts import InquiryDecision


class ReadinessGap(ValueError):
    pass


_MATERIAL_OBSERVATIONS = {
    "event", "pattern", "feedback", "outcome", "comparison",
    "constraint", "preference",
}
_CONCRETE_EXPERIENCE = {"event", "pattern", "feedback", "outcome"}
_DECISION_EVIDENCE = {"constraint", "preference", "comparison", "outcome"}
_SCOPE_RANK = {
    "bounded_guidance": 0,
    "causal_judgment": 1,
    "consequential_decision": 2,
}


def validate_open(decision: InquiryDecision) -> None:
    frame = decision.patch.frame_update
    if decision.operation != "open" or frame is None or frame.mode != "personal":
        return
    if not decision.user_state.states:
        raise ReadinessGap(
            "a newly opened personal Inquiry must capture the user's current state"
        )
    if frame.related_episode_id is not None and not frame.state_delta_required:
        raise ReadinessGap(
            "a related personal episode must require a state delta"
        )
    if frame.state_delta_required and not decision.user_state.deltas and not any(
        item.kind == "state_delta"
        for item in decision.patch.add_blocking_unknowns
    ):
        raise ReadinessGap(
            "a reopened or changing personal topic must capture the state delta "
            "or keep it as a blocking unknown"
        )


def validate_frame_transition(ledger: dict, decision: InquiryDecision) -> None:
    """A revision may strengthen an Inquiry frame, never weaken or relink it."""
    previous = ledger.get("frame")
    proposed = decision.patch.frame_update
    if not isinstance(previous, dict) or proposed is None:
        return
    next_frame = proposed.model_dump()
    if next_frame["mode"] != previous.get("mode"):
        raise ReadinessGap("an Inquiry frame cannot change personal/practical mode")
    if _SCOPE_RANK[next_frame["answer_scope"]] < _SCOPE_RANK.get(
        previous.get("answer_scope"), 0,
    ):
        raise ReadinessGap(
            "the answer scope cannot be downgraded to evade readiness"
        )
    if previous.get("state_delta_required") and not next_frame[
        "state_delta_required"
    ]:
        raise ReadinessGap(
            "state_delta_required cannot be removed from an active Inquiry"
        )
    if next_frame.get("related_episode_id") != previous.get(
        "related_episode_id"
    ):
        raise ReadinessGap(
            "an active Inquiry cannot be relinked to another episode"
        )


def _frame(ledger: dict, decision: InquiryDecision) -> dict | None:
    if decision.patch.frame_update is not None:
        return decision.patch.frame_update.model_dump()
    value = ledger.get("frame")
    return value if isinstance(value, dict) else None


def _observation_kinds(ledger: dict, decision: InquiryDecision) -> set[str]:
    kinds = {
        item.get("kind") for item in ledger.get("observations") or []
        if isinstance(item, dict)
    }
    kinds.update(item.kind for item in decision.patch.add_observations)
    return {kind for kind in kinds if isinstance(kind, str)}


def _count(ledger: dict, key: str, additions: list) -> int:
    return len(ledger.get(key) or []) + len(additions)


def _state_dimensions(ledger: dict, decision: InquiryDecision) -> set[str]:
    dimensions = {
        item.get("dimension") for item in ledger.get("current_state") or []
        if isinstance(item, dict)
    }
    dimensions.update(item.dimension for item in decision.user_state.states)
    return {value for value in dimensions if isinstance(value, str)}


def validate(ledger: dict, decision: InquiryDecision) -> None:
    """Reject a synthesis whose proposed claim strength outruns user evidence.

    Ledgers created before the consultation frame existed retain their legacy
    behavior. Every newly opened Inquiry must carry a frame, so fresh-account
    conversations always use these rails.
    """
    if decision.route != "synthesize":
        return
    frame = _frame(ledger, decision)
    if decision.provisional:
        if decision.operation == "close":
            raise ReadinessGap(
                "a provisional synthesis cannot close the Inquiry"
            )
        if (
            decision.synthesis_basis == "question_budget_exhausted"
            and len(ledger.get("asked_questions") or [])
            < config.inquiry_max_questions()
        ):
            raise ReadinessGap(
                "the question budget is not exhausted; continue Inquiry or use "
                "a user-grounded provisional basis"
            )
        return
    if frame is None:
        return

    kinds = _observation_kinds(ledger, decision)
    state_dimensions = _state_dimensions(ledger, decision)
    states = _count(ledger, "current_state", decision.user_state.states)
    deltas = _count(ledger, "state_deltas", decision.user_state.deltas)
    hypotheses = _count(
        ledger, "hypotheses", decision.patch.add_hypotheses,
    )

    if frame.get("mode") == "personal":
        if states == 0:
            raise ReadinessGap(
                "the user's current state is still missing"
            )
        if frame.get("state_delta_required") and deltas == 0:
            raise ReadinessGap(
                "what changed since the earlier conversation is still missing"
            )
        if (
            not kinds.intersection(_MATERIAL_OBSERVATIONS)
            and "constraint" not in state_dimensions
        ):
            raise ReadinessGap(
                "a concrete experience, constraint, preference, or comparison "
                "from the user is still missing"
            )

    scope = frame.get("answer_scope")
    if scope == "causal_judgment":
        if not kinds.intersection(_CONCRETE_EXPERIENCE):
            raise ReadinessGap(
                "a concrete experience is required for a causal judgment"
            )
        if hypotheses < 2:
            raise ReadinessGap(
                "a causal judgment requires at least two plausible hypotheses"
            )
    elif scope == "consequential_decision":
        if not kinds.intersection(_CONCRETE_EXPERIENCE):
            raise ReadinessGap(
                "a concrete experience is required for a consequential decision"
            )
        if (
            not kinds.intersection(_DECISION_EVIDENCE)
            and "constraint" not in state_dimensions
        ):
            raise ReadinessGap(
                "the user's criteria or constraints are still missing for the "
                "consequential decision"
            )
