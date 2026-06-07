"""Dossier job: rewrite the single narrative 'who you are' doc, folding in the
new span. Compaction is implicit — the prompt caps length, so growth is bounded
(pinned facts live in their own table and are never at risk). Spec §6.3/§8."""
from app.llm.client import chat_json
from app.store import memory, model

_MAX_CHARS = 4000   # soft cap; the model is told to compact toward this

_PROMPT = (
    "You maintain a concise running portrait of a user — who they are: values, "
    "recurring patterns, how they tend to think and decide. Rewrite it by folding "
    "in the NEW conversation span, keeping it under ~{cap} characters (compact and "
    "merge; drop stale detail; this is a narrative, not a log). Respond as strict "
    "JSON: {{\"dossier\": \"<the rewritten portrait>\"}}. Match the user's language.\n\n"
    "## Current portrait\n{prior}\n\n## New conversation span\n{span}"
)


def _span_text(start_turn: int, end_turn: int) -> str:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


async def run(start_turn: int, end_turn: int) -> None:
    span = _span_text(start_turn, end_turn)
    if not span.strip():
        return
    prompt = _PROMPT.format(cap=_MAX_CHARS, prior=model.get_dossier() or "(empty)", span=span)
    try:
        result = await chat_json(system_prompt=prompt, user_prompt="", stage="dossier")
    except Exception:
        return
    text = (result.get("dossier") or "").strip()
    if text:
        model.set_dossier(text)
