"""Rule-scored Inquiry Controller eval over dialogue and Ledger snapshots."""
import json
from pathlib import Path

from app import config
from app.chat import context_plan
from app.inquiry import controller


_DATA = Path(__file__).parent / "data" / "inquiry_cases.json"


def load_cases() -> list[dict]:
    return json.loads(_DATA.read_text())


def _context(case: dict) -> dict:
    messages = case["messages"]
    current = next(
        message for message in reversed(messages) if message["role"] == "user"
    )
    inquiry = case.get("inquiry")
    asked = len(
        (((inquiry or {}).get("ledger") or {}).get("asked_questions") or [])
    )
    max_questions = config.inquiry_max_questions()
    return {
        "stream": case.get("stream", "neutral"),
        "current_user_turn": current,
        "inquiry": inquiry,
        "paused_inquiries": case.get("paused_inquiries", []),
        "recent_messages": [
            message for message in messages
            if message["turn"] != current["turn"]
        ],
        "cited_evidence": case.get("cited_evidence", []),
        "policy": {
            "max_questions": max_questions,
            "questions_asked": asked,
            "remaining_questions": max(0, max_questions - asked),
        },
        "budget": {
            "max_input_tokens": 6000,
            "estimated_tokens": 1000,
            "dropped_recent_messages": 0,
            "dropped_cited_evidence": 0,
            "dropped_paused_inquiries": 0,
        },
    }


def _refs(value: object) -> list[dict]:
    found: list[dict] = []
    if isinstance(value, dict):
        if isinstance(value.get("turn"), int) and isinstance(value.get("quote"), str):
            found.append(value)
        for nested in value.values():
            found.extend(_refs(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_refs(nested))
    return found


def _evidence_valid(decision: dict, case: dict) -> bool:
    user_turns = {
        message["turn"]: message["content"]
        for message in case["messages"] + case.get("cited_evidence", [])
        if message["role"] == "user"
    }
    return all(
        ref["turn"] in user_turns and ref["quote"] in user_turns[ref["turn"]]
        for ref in _refs(decision.get("patch") or {})
    )


def _readiness_valid(decision: dict, context: dict) -> bool:
    if decision["route"] != "synthesize":
        return True
    ledger = ((context.get("inquiry") or {}).get("ledger") or {})
    open_unknowns = [
        item for item in ledger.get("blocking_unknowns") or []
        if item.get("status") == "open"
        and item.get("id") not in (decision.get("patch") or {}).get(
            "resolve_unknown_ids", [],
        )
    ]
    open_unknowns.extend(
        (decision.get("patch") or {}).get("add_blocking_unknowns") or []
    )
    if decision.get("operation") == "close" and open_unknowns:
        return False
    return not open_unknowns or bool(decision.get("provisional"))


def _lock_valid(decision: dict, context: dict) -> bool:
    operation = decision.get("operation")
    inquiry = context.get("inquiry")
    if operation in {"update", "resume", "pause", "close"}:
        if operation == "resume" and inquiry and inquiry.get("status") == "paused":
            candidates = [inquiry, *(context.get("paused_inquiries") or [])]
            return any(
                decision.get("expected_inquiry_id") == candidate.get("id")
                and decision.get("expected_revision") == candidate.get("revision")
                for candidate in candidates
            )
        return bool(
            inquiry
            and decision.get("expected_inquiry_id") == inquiry.get("id")
            and decision.get("expected_revision") == inquiry.get("revision")
        )
    if decision.get("expected_inquiry_id") is not None:
        return False
    if decision.get("expected_revision") is not None:
        return False
    return not (
        inquiry is not None
        and decision.get("route") == "synthesize"
        and operation == "none"
    )


def _target_valid(decision: dict, case: dict) -> bool:
    expected = case.get("expected_target_unknown_id")
    if expected is None or decision.get("target_unknown_id") == expected:
        return True
    patch = decision.get("patch") or {}
    target = decision.get("target_unknown_id")
    added_ids = {
        item.get("id") for item in patch.get("add_blocking_unknowns") or []
    }
    grounded_updates = [
        *(patch.get("add_observations") or []),
        *(patch.get("add_interpretations") or []),
        *(patch.get("add_hypotheses") or []),
    ]
    return bool(
        expected in (patch.get("resolve_unknown_ids") or [])
        and target in added_ids
        and _refs(grounded_updates)
    )


async def run_case(case: dict) -> dict:
    context = _context(case)
    decision_model = await controller.decide(context)
    decision = decision_model.model_dump(mode="json")
    expected = case["expected_route"]
    route_ok = decision["route"] == expected
    actual_context_mode = context_plan.effective_mode(
        decision_model, context["current_user_turn"]["content"],
    )
    expected_context_mode = case.get("expected_context_mode")
    allowed_context_modes = case.get("allowed_context_modes")
    if allowed_context_modes is not None:
        context_mode_ok = actual_context_mode in allowed_context_modes
    elif expected_context_mode is not None:
        context_mode_ok = actual_context_mode == expected_context_mode
    else:
        context_mode_ok = None
    allowed = case.get("allowed_operations")
    operation_ok = allowed is None or decision["operation"] in allowed
    target_ok = _target_valid(decision, case)
    one_question = (
        decision["route"] != "inquire"
        or (
            bool((decision.get("next_question") or "").strip())
            and bool(decision.get("target_unknown_id"))
            and decision.get("answer_brief") is None
        )
    )
    evidence_valid = _evidence_valid(decision, case)
    readiness_valid = _readiness_valid(decision, context)
    lock_valid = _lock_valid(decision, context)
    passed = all((
        route_ok, operation_ok, target_ok, one_question,
        evidence_valid, readiness_valid, lock_valid,
        context_mode_ok is not False,
    ))
    return {
        "id": case.get("id"),
        "expected_route": expected,
        "actual_route": decision["route"],
        "actual_operation": decision["operation"],
        "expected_context_mode": expected_context_mode,
        "allowed_context_modes": allowed_context_modes,
        "actual_context_mode": actual_context_mode,
        "context_mode_ok": context_mode_ok,
        "route_ok": route_ok,
        "operation_ok": operation_ok,
        "target_ok": target_ok,
        "one_question": one_question,
        "evidence_valid": evidence_valid,
        "readiness_valid": readiness_valid,
        "lock_valid": lock_valid,
        "premature_answer": expected == "inquire" and decision["route"] != "inquire",
        "unnecessary_inquiry": expected != "inquire" and decision["route"] == "inquire",
        "passed": passed,
        "decision": decision,
    }
