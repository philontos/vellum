import httpx
import pytest

from app.web import search as websearch


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_tavily_parses_results(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")

    async def fake_post(self, url, headers=None, json=None):
        return _Resp(200, {"results": [
            {"title": "Acme Inc", "url": "https://acme.test",
             "content": "Acme makes rockets."},
        ]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    results = await websearch.search("Acme Inc", max_results=5, depth="basic")
    assert len(results) == 1
    assert results[0].title == "Acme Inc"
    assert results[0].url == "https://acme.test"
    assert "rockets" in results[0].snippet
    # content falls back to the snippet when raw_content is absent (C tier)
    assert "rockets" in results[0].content


@pytest.mark.asyncio
async def test_tavily_prefers_raw_content_when_present(monkeypatch):
    # B tier: when the provider returns full page text, content carries it while
    # snippet stays the short relevant chunk.
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")

    async def fake_post(self, url, headers=None, json=None):
        return _Resp(200, {"results": [
            {"title": "T", "url": "u", "content": "short",
             "raw_content": "the full page body"},
        ]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    results = await websearch.search("q", max_results=5, depth="advanced")
    assert results[0].snippet == "short"
    assert results[0].content == "the full page body"


@pytest.mark.asyncio
async def test_tavily_requires_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        await websearch.search("q", max_results=5, depth="basic")


@pytest.mark.asyncio
async def test_unknown_or_unset_provider_raises(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    with pytest.raises(RuntimeError):
        await websearch.search("q", max_results=5, depth="basic")


@pytest.mark.asyncio
async def test_tavily_http_error_raises(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")

    async def fake_post(self, url, headers=None, json=None):
        return _Resp(429, {"error": "rate limited"})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(RuntimeError, match="429"):
        await websearch.search("q", max_results=5, depth="basic")
