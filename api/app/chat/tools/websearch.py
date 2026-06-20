"""The web_search tool: lets the model look up live information on the open web
— current facts, or a specific company / role / technology / product / person
the user references that the model does not already know. Snippets today (C);
the same structured results extend cleanly to full-page fetch later (B)."""
from app import config
from app.web import search as web

_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the live web for current information, or to learn about a "
            "specific company, role, technology, product, or person the user "
            "refers to that you do not already know. Use a focused query (not the "
            "raw user message). Cross-check multiple results before relying on them."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A focused web search query."}
            },
            "required": ["query"],
        },
    },
}

_MAX_CONTENT_CHARS = 800


def _format(results) -> str:
    blocks = []
    for i, r in enumerate(results, 1):
        body = (r.content or r.snippet or "").strip()
        if len(body) > _MAX_CONTENT_CHARS:
            body = body[:_MAX_CONTENT_CHARS].rstrip() + "…"
        blocks.append(f"[{i}] {r.title}\n{r.url}\n{body}")
    return "\n\n".join(blocks)


async def _handler(args: dict) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "No query provided."
    results = await web.search(
        query,
        max_results=config.web_search_max_results(),
        depth=config.web_search_depth(),
    )
    if not results:
        return "No web results found."
    return _format(results)


def register_into(reg) -> None:
    reg.register(schema=_SCHEMA, handler=_handler)
