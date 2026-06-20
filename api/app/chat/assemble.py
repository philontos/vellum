"""Build the LLM `messages` payload for one chat turn. The current question is
the figure; the personal model + retrieved memory are BACKGROUND REFERENCE,
framed so the model leads with the answer and only leans on them when relevant
(spec §3 altitude)."""
from app import config
from app.chat import persona, retrieval
from app.store import memory, model
from app.store.db import get_conn

_ALTITUDE = (
    "Answer the user's CURRENT question directly and well. Everything below is "
    "BACKGROUND REFERENCE about the user — draw on it only when it genuinely "
    "helps the current question. Do not force it in, do not psychoanalyze the "
    "user, and do not bring up their traits or history unless it is relevant."
)

# Injected only when web search is configured. Turns the raw tool into a
# verification discipline — Vellum should reason from sources like a careful
# analyst, not parrot the first hit.
_RESEARCH_DISCIPLINE = (
    "## Using web search\n"
    "You can search the live web with the `web_search` tool. Use it when the user "
    "refers to a specific company, role, technology, product, or person you do not "
    "already know, or when the question needs current information. Search with a "
    "focused query (you already know facts about the user — use them to make the "
    "query precise). Cross-check multiple sources; distinguish fact from opinion "
    "and attribute views (\"X argues …\"); cite sources inline as Markdown links "
    "[title](url); say so plainly when evidence is thin or sources disagree, and "
    "do not over-claim. Still answer the current question first — do not search "
    "reflexively."
)


def _trait_summary() -> str:
    with get_conn() as conn:
        rows = conn.execute("SELECT dimension FROM trait_current").fetchall()
    parts = []
    for r in rows:
        t = model.get_trait(r["dimension"])
        if not t:
            continue
        scores = {k: v.get("score") for k, v in t["content_json"].items()
                  if isinstance(v, dict) and "score" in v}
        if scores:
            parts.append(f"{r['dimension']}: " +
                         " ".join(f"{k}={round(v)}" for k, v in scores.items()
                                  if v is not None))
    return "\n".join(parts)


async def build_messages(query: str | None = None) -> list[dict]:
    """Assemble system + recent tail. `query` for retrieval defaults to the last
    user message in the tail."""
    tail = memory.recent_tail(config.tail_size())
    if query is None:
        last_user = next((m for m in reversed(tail) if m["role"] == "user"), None)
        query = last_user["content"] if last_user else ""

    sections = [persona.load(), _ALTITUDE]
    if config.web_search_enabled():
        sections.append(_RESEARCH_DISCIPLINE)

    dossier = model.get_dossier().strip()
    if dossier:
        sections.append("## What you know about the user\n" + dossier)

    facts = model.active_facts()
    if facts:
        sections.append("## Durable facts\n" + "\n".join(f"- {f['text']}" for f in facts))

    traits = _trait_summary()
    if traits:
        sections.append("## Personality signal (reference only)\n" + traits)

    if query:
        snips = await retrieval.retrieve(query)
        if snips:
            sections.append("## Possibly relevant past\n" +
                            "\n---\n".join(s["text"] for s in snips))

    system = {"role": "system", "content": "\n\n".join(sections)}
    history = [{"role": m["role"], "content": m["content"]} for m in tail]
    return [system, *history]
