"""Small, evidence-first context for one Inquiry Controller call."""

from app import config
from app.inquiry import budget, store
from app.store import memory


_TRUNCATION_MARKER = "\n[… omitted for controller budget …]\n"


def _public_message(message: dict) -> dict:
    return {
        "turn": message["turn"],
        "role": message["role"],
        "content": message["content"],
    }


def _citation_turns(value: object) -> set[int]:
    turns: set[int] = set()
    if isinstance(value, dict):
        turn = value.get("turn")
        quote = value.get("quote")
        if isinstance(turn, int) and isinstance(quote, str):
            turns.add(turn)
        for nested in value.values():
            turns.update(_citation_turns(nested))
    elif isinstance(value, list):
        for nested in value:
            turns.update(_citation_turns(nested))
    return turns


def _abbreviate(content: str, retained_chars: int) -> str:
    if retained_chars >= len(content):
        return content
    head = (retained_chars + 1) // 2
    tail = retained_chars // 2
    return content[:head] + _TRUNCATION_MARKER + (content[-tail:] if tail else "")


def _clip(value: object, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _paused_summary(inquiry: dict, max_questions: int) -> dict:
    ledger = inquiry["ledger"]
    asked = len(ledger.get("asked_questions") or [])
    return {
        "id": inquiry["id"],
        "revision": inquiry["revision"],
        "goal": _clip((ledger.get("goal") or {}).get("text"), 240),
        "last_turn": inquiry["last_turn"],
        "blocking_unknowns": [
            {
                "id": item.get("id"),
                "question": _clip(item.get("question"), 240),
                "why_material": _clip(item.get("why_material"), 240),
            }
            for item in ledger.get("blocking_unknowns") or []
            if item.get("status") == "open"
        ][:5],
        "provisional_conclusion": _clip(
            ledger.get("provisional_conclusion"), 320,
        ) or None,
        "questions_asked": asked,
        "remaining_questions": max(0, max_questions - asked),
    }


def _fit_current_turn(base: dict, max_tokens: int) -> bool:
    if budget.estimate_tokens(base) <= max_tokens:
        return False
    original = base["current_user_turn"]["content"]
    low, high = 0, len(original)
    best: str | None = None
    while low <= high:
        retained = (low + high) // 2
        candidate = _abbreviate(original, retained)
        base["current_user_turn"]["content"] = candidate
        if budget.estimate_tokens(base) <= max_tokens:
            best = candidate
            low = retained + 1
        else:
            high = retained - 1
    if best is None:
        base["current_user_turn"]["content"] = ""
        if budget.estimate_tokens(base) > max_tokens:
            raise ValueError("Inquiry context budget is smaller than its fixed Ledger")
    else:
        base["current_user_turn"]["content"] = best
    return True


def build(*, stream: str, user_turn: int) -> dict:
    current = memory.get_message_by_turn(user_turn)
    if current is None or current["role"] != "user":
        raise ValueError(f"Turn {user_turn} is not a live user message")

    inquiry = store.get_current(stream)
    inquiry_view = None
    if inquiry is not None:
        inquiry_view = {
            "id": inquiry["id"],
            "status": inquiry["status"],
            "revision": inquiry["revision"],
            "parent_inquiry_id": inquiry["parent_inquiry_id"],
            "ledger": inquiry["ledger"],
        }

    asked = (
        len(inquiry["ledger"].get("asked_questions") or [])
        if inquiry is not None else 0
    )
    max_questions = config.inquiry_max_questions()
    max_tokens = config.inquiry_context_tokens()
    base = {
        "stream": stream,
        "current_user_turn": _public_message(current),
        "inquiry": inquiry_view,
        "paused_inquiries": [],
        "recent_messages": [],
        "cited_evidence": [],
        "policy": {
            "max_questions": max_questions,
            "questions_asked": asked,
            "remaining_questions": max(0, max_questions - asked),
        },
        # Present from the first estimate so the advertised hard limit includes
        # its own diagnostics. Large placeholder counters reserve at least as
        # much serialized space as the final values will need.
        "budget": {
            "max_input_tokens": max_tokens,
            "estimated_tokens": max_tokens,
            "dropped_recent_messages": 99_999,
            "dropped_cited_evidence": 99_999,
            "dropped_paused_inquiries": 99_999,
            "current_user_turn_truncated": False,
        },
    }
    current_truncated = _fit_current_turn(base, max_tokens)

    dropped_paused = 0
    for paused in store.list_paused(stream, limit=5):
        if inquiry is not None and paused["id"] == inquiry["id"]:
            continue
        rendered = _paused_summary(paused, max_questions)
        base["paused_inquiries"].append(rendered)
        if budget.estimate_tokens(base) > max_tokens:
            base["paused_inquiries"].pop()
            dropped_paused += 1

    recent = memory.recent_tail_through(
        config.inquiry_tail_size(), user_turn, stream=stream,
    )
    recent = [message for message in recent if message["turn"] != user_turn]
    recent_turns = {message["turn"] for message in recent}
    cited = []
    if inquiry is not None:
        for turn in sorted(_citation_turns(inquiry["ledger"])):
            if turn in recent_turns:
                continue
            message = memory.get_message_by_turn(turn)
            if message is not None and message["role"] == "user":
                cited.append(message)
    evidence_limit = config.inquiry_evidence_limit()
    cited = cited[-evidence_limit:] if evidence_limit else []

    dropped_cited = 0
    for message in cited:
        rendered = _public_message(message)
        base["cited_evidence"].append(rendered)
        if budget.estimate_tokens(base) > max_tokens:
            base["cited_evidence"].pop()
            dropped_cited += 1

    kept_recent = []
    dropped_recent = 0
    for message in reversed(recent):
        rendered = _public_message(message)
        kept_recent.append(rendered)
        base["recent_messages"] = list(reversed(kept_recent))
        if budget.estimate_tokens(base) > max_tokens:
            kept_recent.pop()
            base["recent_messages"] = list(reversed(kept_recent))
            dropped_recent += 1

    base["budget"].update({
        "dropped_recent_messages": dropped_recent,
        "dropped_cited_evidence": dropped_cited,
        "dropped_paused_inquiries": dropped_paused,
        "current_user_turn_truncated": current_truncated,
    })
    for _ in range(4):
        estimated = budget.estimate_tokens(base)
        if base["budget"]["estimated_tokens"] == estimated:
            break
        base["budget"]["estimated_tokens"] = estimated
    if budget.estimate_tokens(base) > max_tokens:
        current_truncated = _fit_current_turn(base, max_tokens) or current_truncated
        base["budget"]["current_user_turn_truncated"] = current_truncated
        for _ in range(4):
            estimated = budget.estimate_tokens(base)
            if base["budget"]["estimated_tokens"] == estimated:
                break
            base["budget"]["estimated_tokens"] = estimated
    if budget.estimate_tokens(base) > max_tokens:
        raise ValueError("Inquiry context could not be reduced to its hard budget")
    return base
