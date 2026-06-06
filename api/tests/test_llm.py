import httpx
import pytest

from app.llm import client as llm
from app.llm import embed as emb


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_chat_json_parses_object(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")

    async def fake_post(self, url, headers=None, json=None):
        return _Resp(200, {"choices": [{"message": {"content": '{"ok": true}'}}],
                           "usage": {}})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    out = await llm.chat_json(system_prompt="x", user_prompt="y")
    assert out == {"ok": True}


@pytest.mark.asyncio
async def test_embed_returns_vector(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")

    async def fake_post(self, url, headers=None, json=None):
        return _Resp(200, {"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    vec = await emb.embed("hello")
    assert vec == [0.1, 0.2, 0.3]
