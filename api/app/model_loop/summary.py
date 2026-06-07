"""Summary job: digest a turn span into one paragraph (the retrieval handle),
store it, embed it, and index it so it's searchable (spec §6/§8)."""
from app.llm.client import chat_json
from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore

_PROMPT = (
    "Summarize the conversation span below in one tight paragraph: what was "
    "discussed, any conclusion or decision, any commitment made. This is a search "
    "handle for future recall, so be specific. Respond as strict JSON: "
    "{\"summary\": \"<one paragraph>\"}. Match the user's language.\n\n## Span\n"
)


def _span_text(start_turn: int, end_turn: int) -> str:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


async def run(start_turn: int, end_turn: int) -> None:
    span = _span_text(start_turn, end_turn)
    if not span.strip():
        return
    try:
        result = await chat_json(system_prompt=_PROMPT + span, user_prompt="", stage="summary")
    except Exception:
        return
    text = (result.get("summary") or "").strip()
    if not text:
        return
    sid = memory.add_summary(start_turn, end_turn, text)
    label = memory.add_vector_ref("summary", sid)
    VectorStore().add(label, await embed(text))
