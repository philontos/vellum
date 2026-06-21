"""Facts job — a board of DURABLE facts about the user, kept converged.

Every turn, one board-aware LLM call absorbs the new conversation span into the
whole active board at once (`integrate`): seeing what we already know AND the new
span (anchored to its real date), the model returns a changeset —

  add     — genuinely new facts
  update  — an existing fact restated richer/more precise, or corrected because
            the conversation contradicts/supersedes it (store the replacement,
            retire the old id)
  retire  — a fact that no longer holds and has no replacement

Doing perception and integration as a SINGLE board-aware step is what keeps the
board from fragmenting: the model never re-adds a fact it can already see, and it
merges the several facets of one thing said in a conversation into one statement
instead of emitting near-duplicates. Anchoring the span to a real date is what
stops it inventing a year/age for relative time ("今年", "年底").

integrate only reasons about the span in hand, so it can't reach residual
old-vs-old redundancy that no new span happens to touch. So every X turns (gated
on the turn number, no extra runner) run() also runs a whole-board `compact` pass
— the gentle downward force that lets the active set actually shrink, not only
grow. Both steps share ONE definition of a good fact (durable, self-contained,
grounded). Convergence is by redundancy/contradiction, never by age — durable
anchors (allergies, names, locations, identity) stay forever."""
from app import config
from app.llm.client import chat_json
from app.model_loop._span import span_asof_date, span_text
from app.store import model

# One shared definition of a good fact, reused by both integration and compaction
# so "what belongs on the board" can never drift between the two paths.
_FACT_DEF = (
    "A good durable fact is:\n"
    "- DURABLE: allergies, names of close people, location, ongoing projects, hard "
    "preferences, values, identity anchors — and high-order behavioral observations "
    "(e.g. 'tends to internalize unresolved value conflicts as self-doubt'). Keep "
    "these inferred observations; never flatten an insightful one into something "
    "blander.\n"
    "- SELF-CONTAINED: when a fact is bound to a time or situation, write that "
    "premise into the statement itself ('when leaving Foxconn in 2020, interviews "
    "went poorly at first') — never freeze a time-limited state as a standing fact.\n"
    "- GROUNDED: record only specifics (dates, ages, numbers, names) actually stated "
    "in the conversation. Resolve relative time ('this year', 'year-end') against the "
    "given date. NEVER invent or guess a year or age you were not told.\n"
)

_INTEGRATE_PROMPT = (
    "You maintain a board of DURABLE facts about a user. Below is the current board "
    "(each line is 'id. text') and a NEW conversation, as of {date}. Absorb what the "
    "conversation newly tells you, treating it as the latest truth.\n\n"
    + _FACT_DEF +
    "\nReturn a changeset with three lists:\n"
    "- \"update\": something the board ALREADY represents but that you can now state "
    "more richly/precisely, OR that the conversation contradicts or supersedes (the "
    "user moved, changed jobs, reversed a preference). Give {{\"id\": <existing id>, "
    "\"text\": \"<the single best replacement statement>\"}}. Prefer update over "
    "adding a near-duplicate.\n"
    "- \"retire\": ids that are simply no longer true and need no replacement.\n"
    "- \"add\": genuinely new facts not yet represented on the board.\n\n"
    "Rules:\n"
    "- Merge the several facets of the SAME thing seen in this conversation into ONE "
    "statement — do NOT emit multiple near-duplicate adds.\n"
    "- Keep DISTINCT facts distinct: different people or different topics never merge "
    "(a strong-willed mother is not the same fact as a wife firm about parenting).\n"
    "- Leave untouched any fact the conversation does not bear on. When unsure "
    "whether something is durable, leave it out of 'add'.\n\n"
    "Respond as strict JSON: {{\"update\": [{{\"id\": <id>, \"text\": \"...\"}}], "
    "\"retire\": [<id>, ...], \"add\": [\"...\", ...]}} (use [] for any empty list). "
    "Match the user's language.\n\n"
    "## Board\n{board}\n\n## New conversation (as of {date})\n{span}"
)

_COMPACT_PROMPT = (
    "Here is the full board of DURABLE facts about a user. Compact it WITHOUT losing "
    "information.\n\n"
    + _FACT_DEF +
    "\n- MERGE facts that say the same thing, or where one subsumes another, into a "
    "single clear statement that preserves every distinct detail.\n"
    "- RETIRE a fact only when another fact contradicts or supersedes it.\n"
    "- NEVER drop a fact that is still unique and uncontradicted. Keep DISTINCT facts "
    "distinct: different people or different topics never merge.\n\n"
    "Respond as strict JSON: {{\"merge\": [{{\"ids\": [<id>, <id>, ...], \"text\": "
    "\"<merged statement>\"}}], \"retire\": [<id>, ...]}} (use [] when nothing "
    "applies; every merge group needs >=2 ids). Match the user's language.\n\n"
    "## Board\n{board}"
)


def _render_board(active: list[dict]) -> str:
    return "\n".join(f"{f['id']}. {f['text']}" for f in active) or "(empty)"


async def _integrate_plan(span: str, as_of_date: str | None, board: list[dict]) -> dict:
    """The integration brain: one LLM call that sees the whole board AND the dated
    span, returning an {update, retire, add} changeset. Pure compute — NO DB access
    (the board is passed in), so the eval can drive it against an empty board."""
    prompt = _INTEGRATE_PROMPT.format(
        date=as_of_date or "unknown", board=_render_board(board), span=span)
    return await chat_json(system_prompt=prompt, user_prompt="", stage="facts")


def _clean_texts(values) -> list[str]:
    return [v.strip() for v in (values or []) if isinstance(v, str) and v.strip()]


async def extract_facts(span: str, as_of_date: str | None = None) -> list[str]:
    """Pure perception view of the integrator: run it against an EMPTY board, so
    everything perceived lands as an add, and return that cleaned list. The eval
    calls this to measure recall over a cold start; production uses `integrate`."""
    plan = await _integrate_plan(span, as_of_date, [])
    return _clean_texts(plan.get("add"))


def _apply_changeset(plan: dict, active: list[dict], source_turn: int | None) -> None:
    """Apply one integration changeset to the active board. Deterministic and
    defensive: an update/retire id must exist and not already be retired; an update
    needs non-empty text; merged/updated text becomes a fresh row (carrying
    source_turn); an add is inserted only when it isn't an exact duplicate of a
    fact that still stands."""
    by_id = {f["id"]: f for f in active}
    retired: set = set()
    for upd in plan.get("update") or []:
        fid = upd.get("id")
        text = upd.get("text")
        text = text.strip() if isinstance(text, str) else ""
        if fid in by_id and fid not in retired and text:
            model.supersede_fact(fid)
            retired.add(fid)
            model.add_fact(text, source_turn=source_turn)
    for fid in plan.get("retire") or []:
        if fid in by_id and fid not in retired:
            model.supersede_fact(fid)
            retired.add(fid)
    survivors = {by_id[i]["text"].lower() for i in by_id if i not in retired}
    for text in _clean_texts(plan.get("add")):
        if text.lower() not in survivors:
            model.add_fact(text, source_turn=source_turn)
            survivors.add(text.lower())


async def integrate(span: str, as_of_date: str | None, source_turn: int | None) -> None:
    """Absorb one conversation span into the whole active board in a single
    board-aware LLM call. Lets an LLM failure propagate so the runner leaves the
    facts cursor put and retries the span next turn, rather than losing it."""
    active = model.active_facts()
    plan = await _integrate_plan(span, as_of_date, active)
    _apply_changeset(plan, active, source_turn)


def _apply_compaction(plan: dict, active: list[dict]) -> None:
    """Apply a whole-board compaction plan. Same defensive shape as a changeset
    merge: a merge needs >=2 known ids and non-empty text; merged facts become a
    fresh row (source_turn = latest contributing turn) and their originals retire."""
    by_id = {f["id"]: f for f in active}
    for group in plan.get("merge") or []:
        ids = [i for i in (group.get("ids") or []) if i in by_id]
        text = (group.get("text") or "").strip()
        if len(ids) < 2 or not text:
            continue
        turns = [by_id[i]["source_turn"] for i in ids if by_id[i]["source_turn"] is not None]
        model.add_fact(text, source_turn=max(turns) if turns else None)
        for i in ids:
            model.supersede_fact(i)
    for i in plan.get("retire") or []:
        if i in by_id:
            model.supersede_fact(i)


async def compact() -> None:
    """Scan the whole active board and merge residual redundancy in one LLM call.
    No-op when there is nothing to compact."""
    active = model.active_facts()
    if len(active) < 2:
        return
    plan = await chat_json(
        system_prompt=_COMPACT_PROMPT.format(board=_render_board(active)),
        user_prompt="", stage="compact")
    _apply_compaction(plan, active)


async def _maybe_compact(end_turn: int) -> None:
    every = config.facts_compact_every()
    if every <= 0 or end_turn < 0 or end_turn % every != 0:
        return
    try:
        await compact()
    except Exception:
        return


async def run(start_turn: int, end_turn: int) -> None:
    span = span_text(start_turn, end_turn)
    if span.strip():
        await integrate(span, span_asof_date(start_turn, end_turn), end_turn)
    await _maybe_compact(end_turn)
