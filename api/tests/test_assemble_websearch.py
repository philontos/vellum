import pytest

from app.chat import assemble
from app.store import memory


@pytest.mark.asyncio
async def test_research_block_present_when_web_enabled(migrated_db, monkeypatch):
    async def fake_retrieve(q, **kw):
        return []
    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    memory.append_message("user", "hi")
    system = (await assemble.build_messages())[0]["content"]
    assert "web search" in system.lower()
    assert "[title](url)" in system   # inline-citation instruction


@pytest.mark.asyncio
async def test_no_research_block_when_disabled(migrated_db, monkeypatch):
    async def fake_retrieve(q, **kw):
        return []
    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    memory.append_message("user", "hi")
    system = (await assemble.build_messages())[0]["content"]
    assert "web search" not in system.lower()
