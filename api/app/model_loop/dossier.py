"""Dossier job: rewrite the single narrative 'who you are' doc, folding in the
new span. Compaction is implicit — the prompt caps length, so growth is bounded
(pinned facts live in their own table and are never at risk). Spec §6.3/§8."""
from app.llm.client import chat_json
from app.model_loop._span import span_text
from app.store import memory, model

_MAX_CHARS = 4000   # soft cap; the model is told to compact toward this

_PROMPT = (
    "You maintain a concise running portrait of a user — who they are: values, "
    "recurring patterns, how they tend to think and decide. Rewrite it by folding "
    "in the NEW conversation span, keeping it under ~{cap} characters (compact and "
    "merge; drop stale detail; this is a narrative, not a log).\n\n"
    "## Evidence policy\n"
    "- User turns are the primary evidence about the user: their own statements, "
    "choices, reactions, and repeated behavior.\n"
    "- Assistant turns provide conversational context only. They may contain "
    "questions, suggestions, or hypotheses; never absorb an assistant interpretation "
    "into the portrait unless the user clearly confirms it or later user behavior "
    "independently supports it.\n"
    "- A weak acknowledgement such as 'maybe', 'perhaps', 'I guess', '可能吧', or "
    "'也许' is not confirmation.\n"
    "- Do not turn a one-off mood, tentative remark, or isolated event into a stable "
    "personal pattern. When evidence is limited, omit the claim rather than making "
    "the portrait sound more certain or coherent than the user evidence supports.\n"
    "- The current portrait is a provisional prior, not independent evidence. Do "
    "not increase a claim's certainty merely because it already appears there.\n"
    "- Preserve uncertainty for inferred patterns; never rewrite an assistant "
    "hypothesis as a fact.\n\n"
    "Respond as strict "
    "JSON: {{\"dossier\": \"<the rewritten portrait>\"}}. Match the user's language.\n\n"
    "## Current portrait\n{prior}\n\n## New conversation span\n{span}"
)


async def run(start_turn: int, end_turn: int) -> None:
    span = span_text(start_turn, end_turn)
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
