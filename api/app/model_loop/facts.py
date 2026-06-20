"""Facts job. Two steps per turn:

  extract     — pull durable, pinnable facts from the new span (pure; the eval
                calls extract_facts directly to measure recall).
  reconcile   — for EACH new fact, one focused LLM call judges it against the full
                active board plus the conversation it came from, and decides:
                  add        — genuinely new
                  duplicate  — already on the board; change nothing
                  update     — contradicts/supersedes/refines existing fact(s):
                               store the best replacement, retire the old id(s)

Reconciling one fact at a time (with the raw span and the whole board in view)
keeps each decision accurate — the model isn't splitting attention across many
facts, and nothing is hidden by retrieval. This is what keeps the board converged
and contradiction-free instead of growing without bound. Each fact is best-effort
and isolated: one failure never blocks the others.

Facts are DURABLE anchors (allergies, names, locations, identity). Convergence is
by redundancy/contradiction, never by age — those anchors are never dropped."""
from app import config
from app.llm.client import chat_json
from app.model_loop._span import span_text
from app.store import model

_PROMPT = (
    "Extract DURABLE, pinnable facts about the user from the conversation span "
    "below — things worth always remembering: allergies, names of people close to "
    "them, location, ongoing projects, hard preferences, identity anchors. Do NOT "
    "extract transient states, opinions in flux, or one-off events. Respond as "
    "strict JSON: {\"facts\": [\"<short factual statement>\", ...]} (empty list if "
    "none). Match the user's language.\n\n## Conversation span\n"
)

_RECONCILE_PROMPT = (
    "You maintain a board of DURABLE facts about a user. A NEW fact was just "
    "observed. Decide how it reconciles with the existing board, treating the NEW "
    "fact (and the conversation it came from) as the latest truth.\n\n"
    "Choose ONE action:\n"
    "- \"add\": genuinely new — not already represented on the board.\n"
    "- \"duplicate\": the board already states this; change nothing.\n"
    "- \"update\": it contradicts, supersedes, or refines one or more existing "
    "facts (the user moved, changed jobs, reversed a preference, ...). Give the "
    "single best replacement statement and list the id(s) it retires.\n\n"
    "Rules: NEVER retire a fact that is still unique and uncontradicted. Do not "
    "retire by age — durable anchors (allergies, names, locations, identity) stay "
    "forever. Keep the board concise (ideally <= {target} facts) by preferring "
    "'update'/merge over piling on near-duplicates, but never drop a unique, "
    "uncontradicted fact just to hit a number.\n\n"
    "Respond as strict JSON: {{\"action\": \"add|duplicate|update\", \"text\": "
    "\"<statement to store; omit for duplicate>\", \"retire\": [<id>, ...]}}. "
    "Match the user's language.\n\n"
    "## New fact\n{fact}\n\n## From this conversation\n{span}\n\n## Existing board\n{board}"
)


async def extract_facts(span: str) -> list[str]:
    """Extract durable facts from a span. Pure compute — NO DB write. The eval
    calls this directly and measures recall; production `run()` reconciles + persists."""
    result = await chat_json(system_prompt=_PROMPT + span, user_prompt="", stage="facts")
    return [f.strip() for f in (result.get("facts") or []) if isinstance(f, str) and f.strip()]


def _apply_decision(decision: dict, active: list[dict], source_turn: int | None) -> None:
    """Apply one reconcile decision to the active board. Deterministic and
    defensive: 'duplicate' is a no-op; retire ids must exist; a new statement is
    added only if non-empty and not an exact duplicate of a surviving fact."""
    if (decision.get("action") or "").lower() == "duplicate":
        return
    valid = {f["id"] for f in active}
    retire = [i for i in (decision.get("retire") or []) if i in valid]
    for i in retire:
        model.supersede_fact(i)
    text = (decision.get("text") or "").strip()
    if not text:
        return
    survivors = {f["text"].lower() for f in active if f["id"] not in set(retire)}
    if text.lower() not in survivors:
        model.add_fact(text, source_turn=source_turn)


async def reconcile_one(fact: str, span: str, source_turn: int | None) -> None:
    """Reconcile a single new fact against the full active board. With nothing to
    reconcile against, the fact is simply added (no LLM call needed)."""
    active = model.active_facts()
    if not active:
        model.add_fact(fact, source_turn=source_turn)
        return
    board = "\n".join(f"{f['id']}. {f['text']}" for f in active)
    prompt = _RECONCILE_PROMPT.format(
        target=config.facts_target_count(), fact=fact, span=span, board=board)
    decision = await chat_json(system_prompt=prompt, user_prompt="", stage="reconcile")
    _apply_decision(decision, active, source_turn)


async def run(start_turn: int, end_turn: int) -> None:
    span = span_text(start_turn, end_turn)
    if not span.strip():
        return
    try:
        new_facts = await extract_facts(span)
    except Exception:
        return
    for fact in new_facts:
        try:
            await reconcile_one(fact, span, end_turn)
        except Exception:
            continue
