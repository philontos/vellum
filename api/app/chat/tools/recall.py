"""The recall_memory tool (B): lets the model issue a targeted/iterative memory
query with a well-formed search string."""
from app.chat import retrieval

_SCHEMA = {
    "type": "function",
    "function": {
        "name": "recall_memory",
        "description": (
            "Search the user's long-term memory for past conversations relevant "
            "to a query. Use when the user references something from the past, or "
            "when prior context would materially help — with a focused query "
            "(not the raw user message)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."}
            },
            "required": ["query"],
        },
    },
}


def register_into(reg, stream: str = "neutral") -> None:
    async def _handler(args: dict) -> str:
        snips = await retrieval.retrieve(args.get("query", ""), stream=stream)
        if not snips:
            return "No relevant past conversations found."
        return "\n---\n".join(s["text"] for s in snips)

    reg.register(schema=_SCHEMA, handler=_handler)
