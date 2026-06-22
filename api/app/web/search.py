"""Web search client — a provider abstraction for live web lookups (mirrors the
shape of llm/embed.py). This is the backend web-access package; unrelated to the
top-level `/web` frontend.

Configure with:

    WEB_SEARCH_PROVIDER   "" (disabled, default) | "tavily"
    TAVILY_API_KEY        your Tavily key (when provider=tavily)
    WEB_SEARCH_TIMEOUT_SECONDS   default: 20

Results are returned as a uniform `SearchResult` list. `snippet` is always the
short relevant chunk; `content` is the fullest text the provider gave (the
snippet today / full page body once a deeper search depth or a `fetch_url` tool
is added — the field shape stays the same so the model never relearns it)."""

import os
from dataclasses import dataclass

import httpx

_DEFAULT_TIMEOUT = float(os.getenv("WEB_SEARCH_TIMEOUT_SECONDS", "20"))
_TAVILY_URL = "https://api.tavily.com/search"


class WebSearchNotConfigured(RuntimeError):
    """No usable provider/credential. A *configuration* gap, not a runtime fault —
    so the tool handler can answer the model gracefully ("search isn't available")
    instead of surfacing a raw error. Genuine provider failures stay as plain
    exceptions and bubble up to be wrapped as an ERROR result."""


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str   # short relevant chunk
    content: str   # fullest text available (>= snippet)


async def search(query: str, *, max_results: int, depth: str) -> list[SearchResult]:
    """Resolve the configured provider and run the search. Adding a backup
    provider later is a single `elif` here (each raises WebSearchNotConfigured
    when its own credential is missing, so callers handle the gap uniformly)."""
    provider = (os.getenv("WEB_SEARCH_PROVIDER") or "").strip().lower()
    if provider == "tavily":
        return await _tavily(query, max_results=max_results, depth=depth)
    raise WebSearchNotConfigured(
        f"Web search not configured. Set WEB_SEARCH_PROVIDER (got {provider!r})."
    )


async def _tavily(query: str, *, max_results: int, depth: str) -> list[SearchResult]:
    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise WebSearchNotConfigured(
            "Tavily web search not configured. Set TAVILY_API_KEY.")

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": depth,          # "basic" (C) | "advanced" (deeper, B)
        "include_raw_content": depth == "advanced",
    }
    async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT) as client:
        resp = await client.post(_TAVILY_URL, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Web search request failed: status={resp.status_code} body={resp.text[:400]}"
        )
    data = resp.json()
    results = []
    for r in data.get("results") or []:
        snippet = (r.get("content") or "").strip()
        results.append(SearchResult(
            title=(r.get("title") or "").strip(),
            url=(r.get("url") or "").strip(),
            snippet=snippet,
            # raw_content only present on deeper searches; fall back to snippet.
            content=(r.get("raw_content") or snippet),
        ))
    return results
