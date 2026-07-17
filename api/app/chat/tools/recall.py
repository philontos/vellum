"""The recall_memory tool (B): lets the model issue a targeted/iterative memory
query with a well-formed search string."""
from app.chat import retrieval
from app.prompts import runtime


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
) -> None:
    async def _handler(args: dict) -> str:
        if through_turn is None:
            snips = await retrieval.retrieve(args.get("query", ""), stream=stream)
        else:
            snips = await retrieval.retrieve(
                args.get("query", ""), stream=stream,
                through_turn=through_turn,
            )
        if not snips:
            return "No relevant past conversations found."
        return "\n---\n".join(s["text"] for s in snips)

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
