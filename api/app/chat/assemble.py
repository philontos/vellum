"""Build the LLM `messages` payload for one chat turn. The current question is
the figure; the personal model + retrieved memory are BACKGROUND REFERENCE,
framed so the model leads with the answer and only leans on them when relevant
(spec §3 altitude)."""
from app import config
from app.chat import persona, retrieval
from app.config.dimensions_loader import dimension_meta
from app.store import memory, model
from app.store.db import get_conn

# Default altitude framing for the thinking-partner mode. A persona can replace it
# wholesale by shipping its own stance.txt (e.g. the counseling mode), in which case
# `persona.stance` is used here instead — see build_messages.
_ALTITUDE = (
    "Answer the user's CURRENT question directly and well. Everything below is "
    "BACKGROUND REFERENCE about the user — draw on it when it genuinely helps the "
    "current question, not for its own sake. When their patterns, reasoning, or "
    "blind spots bear on the question, real insight — including naming a weakness "
    "or a piece of self-deception — is part of helping. Read not just what they "
    "say but how they say it (phrasing, emphasis, recurring habits), and cross-"
    "check against the personality model below to sharpen or temper a read and to "
    "tailor advice. Keep every read genuine and grounded — never manufactured, "
    "never performed, and don't recite their traits back as labels."
)

# Injected only when web search is configured. Frames web_search as a general
# "stay current / fill knowledge gaps" capability — used broadly, but referenced
# like a careful analyst: weigh sources, don't parrot the first hit.
_RESEARCH_DISCIPLINE = (
    "## Using web search\n"
    "You have a fixed knowledge cutoff and your training data can be incomplete or "
    "out of date. You can search the live web with the `web_search` tool — use it "
    "freely whenever current, time-sensitive, or outside information would make "
    "your answer more accurate or complete, or when you are not confident you know "
    "something (you needn't search what you already know well). Use a focused query "
    "— you already know facts about the user, so use them to make it precise. Treat "
    "results as evidence to weigh, not as truth: cross-check across sources, "
    "distinguish fact from opinion and attribute views (\"X argues …\"), cite "
    "sources inline as Markdown links [title](url), and say plainly when evidence "
    "is thin, sources disagree, or you remain unsure. Answer the user's current "
    "question directly — let search support your answer, not replace your judgment."
)


# Frames the trait block as a diagnostic lens, not décor: use it to understand
# the user past their own words and to surface blind spots / weak points / mental
# ruts with sharp, honest help — but treat the scores as hypotheses to test
# against what they actually say, never as verdicts to recite back.
_TRAIT_FRAME = (
    "A measured psychological read of the user. Use it to understand them past "
    "their own words — to anticipate their blind spots, weak points, and habitual "
    "thinking patterns. When it matters, name those directly and give sharp, "
    "honest, genuinely useful help, even when it's uncomfortable. Treat the scores "
    "as hypotheses to test against what the user actually says, not as verdicts "
    "about who they are; surface a pattern only when their words bear it out. Never "
    "recite the traits back as labels."
)


def _band(score: float) -> str:
    """Deterministic high/moderate/low gloss for a 0-100 unipolar score."""
    if score > 60:
        return "high"
    if score < 40:
        return "low"
    return "moderate"


def _render_sub(sub: dict, score: float) -> str:
    """One sub-dimension read: named band for unipolar, pole lean for bipolar.
    `poles` = [label@0, label@100]; 50 is balanced."""
    s = round(score)
    poles = sub.get("poles")
    if poles:
        low, high = poles
        dist = abs(score - 50)
        if dist <= 10:
            return f"balanced {low}/{high} ({s})"
        pole = low if score < 50 else high
        strength = "leans" if dist <= 25 else "strongly"
        return f"{strength} {pole} ({s})"
    return f"{sub['name']}: {_band(score)} ({s})"


def _trait_summary() -> str:
    with get_conn() as conn:
        rows = conn.execute("SELECT dimension FROM trait_current").fetchall()
    lines = []
    for r in rows:
        key = r["dimension"]
        t = model.get_trait(key)
        if not t:
            continue
        scores = {k: v.get("score") for k, v in t["content_json"].items()
                  if isinstance(v, dict) and v.get("score") is not None}
        if not scores:
            continue
        meta = dimension_meta(key)
        if not meta:   # unknown/disabled dimension still on the board — render raw
            lines.append(f"- {key}: " +
                         ", ".join(f"{k}={round(v)}" for k, v in scores.items()))
            continue
        parts = [_render_sub(sub, scores[sub["key"]])
                 for sub in meta["sub_dimensions"] if scores.get(sub["key"]) is not None]
        if parts:
            lines.append(f"- {meta['name']}: " + ", ".join(parts))
    return "\n".join(lines)


async def build_messages(query: str | None = None,
                         persona_name: str | None = None) -> list[dict]:
    """Assemble system + recent tail. `query` for retrieval defaults to the last
    user message in the tail. `persona_name` selects the prompt-side mode (voice +
    stance); None falls back to VELLUM_PERSONA."""
    tail = memory.recent_tail(config.tail_size())
    if query is None:
        last_user = next((m for m in reversed(tail) if m["role"] == "user"), None)
        query = last_user["content"] if last_user else ""

    p = persona.load(persona_name)
    sections = [p.voice, p.stance or _ALTITUDE]
    if config.web_search_configured():
        sections.append(_RESEARCH_DISCIPLINE)

    dossier = model.get_dossier().strip()
    if dossier:
        sections.append("## What you know about the user\n" + dossier)

    facts = model.active_facts()
    if facts:
        sections.append("## Durable facts\n" + "\n".join(f"- {f['text']}" for f in facts))

    traits = _trait_summary()
    if traits:
        sections.append("## How the user tends to be\n" +
                        (p.trait_frame or _TRAIT_FRAME) + "\n\n" + traits)

    if query:
        snips = await retrieval.retrieve(query)
        if snips:
            sections.append("## Possibly relevant past\n" +
                            "\n---\n".join(s["text"] for s in snips))

    system = {"role": "system", "content": "\n\n".join(sections)}
    history = [{"role": m["role"], "content": m["content"]} for m in tail]
    return [system, *history]
