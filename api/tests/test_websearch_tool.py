import pytest

from app.chat.tools import registry, websearch
from app.web.search import SearchResult


@pytest.mark.asyncio
async def test_web_search_tool_registered_and_formats(monkeypatch):
    async def fake_search(q, **kw):
        return [
            SearchResult(title="Acme", url="https://acme.test",
                         snippet="rockets", content="Acme makes rockets."),
            SearchResult(title="Beta", url="https://beta.test",
                         snippet="boats", content="Beta makes boats."),
        ]
    monkeypatch.setattr(websearch.web, "search", fake_search)
    reg = registry.ToolRegistry()
    websearch.register_into(reg)
    assert "web_search" in [t["function"]["name"] for t in reg.schemas()]
    out = await reg.adispatch("web_search", {"query": "Acme"})
    assert "Acme" in out and "https://acme.test" in out
    assert "rockets" in out
    assert "Beta" in out and "https://beta.test" in out


@pytest.mark.asyncio
async def test_web_search_empty_results(monkeypatch):
    async def fake_search(q, **kw):
        return []
    monkeypatch.setattr(websearch.web, "search", fake_search)
    out = await websearch._handler({"query": "nothing here"})
    assert out == "No web results found."


@pytest.mark.asyncio
async def test_web_search_blank_query_short_circuits():
    out = await websearch._handler({"query": "   "})
    assert out == "No query provided."


@pytest.mark.asyncio
async def test_web_search_truncates_long_content(monkeypatch):
    long_body = "x" * 5000

    async def fake_search(q, **kw):
        return [SearchResult(title="T", url="https://t.test",
                             snippet="s", content=long_body)]
    monkeypatch.setattr(websearch.web, "search", fake_search)
    out = await websearch._handler({"query": "q"})
    assert "…" in out                       # truncation marker
    assert out.count("x") < len(long_body)  # body was cut down


@pytest.mark.asyncio
async def test_web_search_handler_error_wrapped_by_registry(monkeypatch):
    async def boom(q, **kw):
        raise RuntimeError("provider exploded")
    monkeypatch.setattr(websearch.web, "search", boom)
    reg = registry.ToolRegistry()
    websearch.register_into(reg)
    out = await reg.adispatch("web_search", {"query": "q"})
    assert out.startswith("ERROR running web_search")
