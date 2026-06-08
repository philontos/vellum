"""Facts job (eager): extract durable, pinnable facts about the user from a span
and add the new ones (dedup against active facts). MVP — supersession of facts
that become false is a later refinement."""
from app.llm.client import chat_json
from app.model_loop._span import span_text
from app.store import memory, model

_PROMPT = (
    "Extract DURABLE, pinnable facts about the user from the conversation span "
    "below — things worth always remembering: allergies, names of people close to "
    "them, location, ongoing projects, hard preferences, identity anchors. Do NOT "
    "extract transient states, opinions in flux, or one-off events. Respond as "
    "strict JSON: {\"facts\": [\"<short factual statement>\", ...]} (empty list if "
    "none). Match the user's language.\n\n## Conversation span\n"
)


async def extract_facts(span: str) -> list[str]:
    """Extract durable facts from a span. Pure compute — NO DB write. The eval
    calls this directly and measures recall; production `run()` dedups + persists."""
    result = await chat_json(system_prompt=_PROMPT + span, user_prompt="", stage="facts")
    return [f.strip() for f in (result.get("facts") or []) if isinstance(f, str) and f.strip()]


async def run(start_turn: int, end_turn: int) -> None:
    span = span_text(start_turn, end_turn)
    if not span.strip():
        return
    try:
        new_facts = await extract_facts(span)
    except Exception:
        return
    existing = {f["text"].lower() for f in model.active_facts()}
    for text in new_facts:
        if text.lower() not in existing:
            model.add_fact(text, source_turn=end_turn)
            existing.add(text.lower())
