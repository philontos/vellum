"""The recall_memory tool (B): lets the model issue a targeted/iterative memory
query with a well-formed search string."""
from app.chat import retrieval
from app.prompts import runtime
from app.token_budget import clip_text


_DESCRIPTION = (
    "Search the user's long-term memory for past conversations relevant "
    "to a query. Use when the user references something from the past, or "
    "when prior context would materially help — with a focused query "
    "(not the raw user message)."
)

_SCHEMA = {
    "type": "function",
    "function": {
        "name": "recall_memory",
        "description": _DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."}
            },
            "required": ["query"],
        },
    },
}


def register_into(
    reg, stream: str = "neutral", through_turn: int | None = None,
    exclude_turns: set[int] | None = None, summary_mode: str = "raw",
    max_tokens: int | None = None,
) -> None:
    async def _handler(args: dict) -> str:
        snips = await retrieval.retrieve(
            args.get("query", ""), stream=stream,
            through_turn=through_turn,
            exclude_turns=set(exclude_turns or ()),
            summary_mode=summary_mode,
        )
        if not snips:
            return "No relevant past conversations found."
        result = "\n---\n".join(s["text"] for s in snips)
        if max_tokens is None:
            return result
        clipped, _ = clip_text(
            result, max_tokens,
            omission_marker="\n[… omitted for recall budget …]\n",
        )
        return clipped or "No recall result fits the responder context budget."

    schema = {
        **_SCHEMA,
        "function": {
            **_SCHEMA["function"],
            "description": runtime.resolve(
                "tool.recall_memory.description", _DESCRIPTION,
            ),
        },
    }
    reg.register(schema=schema, handler=_handler)
