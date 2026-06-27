"""Summary job: digest a turn span into one paragraph (the retrieval handle),
store it, embed it, and index it so it's searchable (spec §6/§8)."""
from app.llm.client import chat_json
from app.llm.embed import embed
from app.model_loop._span import span_text
from app.store import memory
from app.store.vectors import VectorStore

_PROMPT = (
    "Summarize the conversation span below in one tight paragraph: what was "
    "discussed, any conclusion or decision, any commitment made. This is a search "
    "handle for future recall, so be specific. Respond as strict JSON: "
    "{\"summary\": \"<one paragraph>\"}. Match the user's language.\n\n## Span\n"
)


async def run(start_turn: int, end_turn: int, stream: str = "neutral") -> None:
    """Digest `stream`'s turns within [start, end] into one searchable card. The
    span is scoped to the stream so a counseling card never contains daily turns
    (and vice versa); recall stays per-stream off the resulting vector."""
    span = span_text(start_turn, end_turn, stream=stream)
    if not span.strip():
        return
    try:
        result = await chat_json(system_prompt=_PROMPT + span, user_prompt="", stage="summary")
    except Exception:
        return
    text = (result.get("summary") or "").strip()
    if not text:
        return
    sid = memory.add_summary(start_turn, end_turn, text, stream=stream)
    label = memory.add_vector_ref("summary", sid)
    VectorStore().add(label, await embed(text))
