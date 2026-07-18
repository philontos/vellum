"""Deterministic validation, state transitions, and Ledger patch application."""
import json
from dataclasses import dataclass, replace

from app import config
from app.inquiry import budget, store
from app.inquiry.contracts import EvidenceRef, InquiryDecision
from app.store import memory


class InquiryApplicationError(RuntimeError):
    pass


class EvidenceValidationError(InquiryApplicationError):
    pass


class InvalidTransitionError(InquiryApplicationError):
    pass


class NotReadyError(InquiryApplicationError):
    pass


class RepeatedQuestionError(InquiryApplicationError):
    pass


class QuestionBudgetExceededError(InquiryApplicationError):
    pass


class LedgerCapacityError(InquiryApplicationError):
    pass


class UngroundedResolutionError(InquiryApplicationError):
    pass


@dataclass(frozen=True)
class AppliedDecision:
    decision: InquiryDecision
    inquiry: dict | None
    user_reply: str | None
    close_pending: bool = False


def empty_ledger() -> dict:
    return {
        "goal": None,
        "observations": [],
        "interpretations": [],
        "hypotheses": [],
        "blocking_unknowns": [],
        "asked_questions": [],
        "provisional_conclusion": None,
    }


def _copy(value: dict) -> dict:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _validate_ledger_capacity(ledger: dict) -> None:
    if budget.estimate_tokens(ledger) > config.inquiry_ledger_tokens():
        raise LedgerCapacityError(
            "Inquiry Ledger exceeds its bounded controller-context allocation"
        )


def _validate_ref(ref: EvidenceRef, stream: str) -> None:
    message = memory.get_message_by_turn(ref.turn)
    if (
        message is None
        or message["role"] != "user"
        or message["stream"] != stream
    ):
        raise EvidenceValidationError(
            f"Evidence turn {ref.turn} is not a live user message in this stream"
        )
    if ref.quote not in message["content"]:
        raise EvidenceValidationError(
            f"Evidence quote is not present in user turn {ref.turn}"
        )


def _validate_evidence(decision: InquiryDecision, stream: str) -> None:
    patch = decision.patch
    groups = []
    if patch.goal_update is not None:
        groups.append(patch.goal_update.evidence)
    groups.extend(item.evidence for item in patch.add_observations)
    groups.extend(item.evidence for item in patch.add_interpretations)
    for item in patch.add_hypotheses:
        groups.extend((item.supporting_evidence, item.disconfirming_evidence))
    for refs in groups:
        for ref in refs:
            _validate_ref(ref, stream)


def _has_grounded_resolution_evidence(decision: InquiryDecision) -> bool:
    patch = decision.patch
    if not patch.resolve_unknown_ids:
        return True
    return any((
        patch.add_observations,
        patch.add_interpretations,
        any(
            item.supporting_evidence or item.disconfirming_evidence
            for item in patch.add_hypotheses
        ),
    ))


def _next_id(items: list[dict], prefix: str) -> str:
    used = {item.get("id") for item in items}
    number = 1
    while f"{prefix}{number}" in used:
        number += 1
    return f"{prefix}{number}"


def _refs(items) -> list[dict]:
    return [item.model_dump() for item in items]


def _append_unique(target: list[dict], item: dict) -> None:
    if not any(existing.get("text") == item.get("text") for existing in target):
        target.append(item)


def _apply_patch(ledger: dict, decision: InquiryDecision, user_turn: int) -> dict:
    result = _copy(ledger)
    patch = decision.patch
    if patch.goal_update is not None:
        result["goal"] = patch.goal_update.model_dump()

    for draft in patch.add_observations:
        _append_unique(result["observations"], {
            "id": _next_id(result["observations"], "o"),
            "text": draft.text,
            "evidence": _refs(draft.evidence),
        })
    for draft in patch.add_interpretations:
        _append_unique(result["interpretations"], {
            "id": _next_id(result["interpretations"], "i"),
            "text": draft.text,
            "evidence": _refs(draft.evidence),
        })
    for draft in patch.add_hypotheses:
        _append_unique(result["hypotheses"], {
            "id": _next_id(result["hypotheses"], "h"),
            "text": draft.text,
            "supporting_evidence": _refs(draft.supporting_evidence),
            "disconfirming_evidence": _refs(draft.disconfirming_evidence),
        })

    unknowns = result["blocking_unknowns"]
    by_id = {item["id"]: item for item in unknowns}
    for draft in patch.add_blocking_unknowns:
        if draft.id in by_id:
            raise InquiryApplicationError(f"Duplicate blocking unknown {draft.id!r}")
        item = {
            **draft.model_dump(),
            "status": "open",
            "resolved_after_turn": None,
        }
        unknowns.append(item)
        by_id[draft.id] = item
    for unknown_id in patch.resolve_unknown_ids:
        item = by_id.get(unknown_id)
        if item is None:
            raise InquiryApplicationError(f"Unknown blocking unknown {unknown_id!r}")
        item["status"] = "resolved"
        item["resolved_after_turn"] = user_turn

    if patch.provisional_conclusion is not None:
        result["provisional_conclusion"] = patch.provisional_conclusion

    if decision.route == "inquire":
        target = by_id.get(decision.target_unknown_id)
        if target is None or target["status"] != "open":
            raise InquiryApplicationError(
                "The next question must target an open blocking unknown"
            )
        normalized = " ".join(decision.next_question.split()).casefold()
        if any(
            " ".join((asked.get("text") or "").split()).casefold() == normalized
            for asked in result["asked_questions"]
        ):
            raise RepeatedQuestionError("The same inquiry question was already asked")
        if len(result["asked_questions"]) >= config.inquiry_max_questions():
            raise QuestionBudgetExceededError(
                "Inquiry question budget exhausted; synthesize provisionally or pause"
            )
        result["asked_questions"].append({
            "unknown_id": decision.target_unknown_id,
            "text": decision.next_question,
            "after_turn": user_turn,
        })
    return result


def _status_after(current: dict, decision: InquiryDecision) -> str:
    before = current["status"]
    operation = decision.operation
    allowed = {
        "exploring": {"update", "pause", "close"},
        "reviewing": {"update", "pause", "close"},
        "paused": {"resume", "close"},
    }
    if operation not in allowed.get(before, set()):
        raise InvalidTransitionError(f"Cannot {operation} an inquiry in {before}")
    if operation == "pause":
        return "paused"
    if operation == "close":
        return "closed"
    if decision.route == "synthesize":
        return "reviewing"
    return "exploring"


def _open_unknowns(ledger: dict) -> list[dict]:
    return [
        item for item in ledger["blocking_unknowns"]
        if item.get("status") == "open"
    ]


def _revision_target(decision: InquiryDecision, stream: str) -> dict:
    target = store.get(decision.expected_inquiry_id or -1)
    active = store.get_active(stream)
    operation = decision.operation
    eligible = bool(target and target["stream"] == stream)
    if eligible and operation == "resume":
        eligible = target["status"] == "paused" and active is None
    elif eligible and operation == "close" and target["status"] == "paused":
        eligible = active is None
    elif eligible:
        eligible = bool(
            target["status"] in {"exploring", "reviewing"}
            and active is not None
            and active["id"] == target["id"]
        )
    if not eligible or target["revision"] != decision.expected_revision:
        found = "none" if target is None else (
            f"{target['id']}@{target['revision']}:{target['status']}"
        )
        raise store.RevisionConflictError(
            "Expected resumable/current inquiry "
            f"{decision.expected_inquiry_id}@{decision.expected_revision}, "
            f"found {found}"
        )
    return target


def apply_decision(
    decision: InquiryDecision, *, stream: str, user_turn: int,
    run_id: str | None, defer_close: bool = False,
) -> AppliedDecision:
    replay = store.get_by_run_id(run_id)
    if replay is not None:
        return AppliedDecision(
            decision, replay,
            decision.next_question if decision.route == "inquire" else None,
            close_pending=(
                decision.operation == "close" and replay["status"] != "closed"
            ),
        )
    if not _has_grounded_resolution_evidence(decision):
        raise UngroundedResolutionError(
            "Resolving a blocking unknown requires a grounded Ledger claim"
        )
    _validate_evidence(decision, stream)
    current = store.get_current(stream)

    if decision.operation == "none":
        if decision.route == "synthesize" and current is not None:
            raise InvalidTransitionError(
                "An active inquiry synthesis must advance its revision"
            )
        return AppliedDecision(decision, current, None)

    if decision.operation == "open":
        ledger = _apply_patch(empty_ledger(), decision, user_turn)
        _validate_ledger_capacity(ledger)
        parent = store.latest_for_stream(stream)
        inquiry = store.open_inquiry(
            stream=stream,
            opened_turn=user_turn,
            ledger=ledger,
            decision=decision.model_dump(),
            run_id=run_id,
            parent_inquiry_id=(
                parent["id"] if parent is not None and parent["status"] == "closed"
                else None
            ),
        )
        return AppliedDecision(decision, inquiry, decision.next_question)

    current = _revision_target(decision, stream)

    ledger = _apply_patch(current["ledger"], decision, user_turn)
    _validate_ledger_capacity(ledger)
    open_unknowns = _open_unknowns(ledger)
    if decision.route == "synthesize" and open_unknowns and not decision.provisional:
        raise NotReadyError("Material blocking unknowns remain open")
    if decision.operation == "close" and open_unknowns:
        raise NotReadyError("A closed inquiry cannot retain blocking unknowns")

    close_pending = defer_close and decision.operation == "close"
    resolved_status = _status_after(current, decision)
    status = "reviewing" if close_pending else resolved_status
    action = "synthesize" if close_pending else (
        decision.operation
        if decision.operation in {"resume", "pause", "close"}
        else decision.route
    )
    inquiry = store.apply_revision(
        inquiry_id=current["id"],
        expected_revision=current["revision"],
        status=status,
        ledger=ledger,
        action=action,
        user_turn=user_turn,
        decision=decision.model_dump(),
        run_id=run_id,
    )
    return AppliedDecision(
        decision, inquiry,
        decision.next_question if decision.route == "inquire" else None,
        close_pending=close_pending,
    )


def finalize_deferred_close(
    applied: AppliedDecision, *, user_turn: int, run_id: str | None,
) -> AppliedDecision:
    """Close only after the synthesized assistant answer is durably stored."""
    if not applied.close_pending:
        return applied
    if applied.inquiry is None:
        raise InvalidTransitionError("A deferred close has no Inquiry")
    closed = store.apply_revision(
        inquiry_id=applied.inquiry["id"],
        expected_revision=applied.inquiry["revision"],
        status="closed",
        ledger=applied.inquiry["ledger"],
        action="close",
        user_turn=user_turn,
        decision={
            **applied.decision.model_dump(mode="json"),
            "delivery_finalized": True,
        },
        run_id=run_id,
    )
    return replace(applied, inquiry=closed, close_pending=False)
