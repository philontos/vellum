import httpx
import pytest

from app.llm import client as llm


class _FakeStream:
    """Minimal stand-in for httpx's streaming response context manager."""
    def __init__(self, lines, status=200):
        self._lines = lines
        self.status_code = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def aiter_lines(self):
        for ln in self._lines:
            yield ln

    async def aread(self):
        return b""


@pytest.mark.asyncio
async def test_stream_yields_reasoning_delta(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "deepseek-reasoner")
    lines = [
        'data: {"choices":[{"delta":{"reasoning_content":"let me think"}}]}',
        'data: {"choices":[{"delta":{"content":"answer"}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
        "data: [DONE]",
    ]
    monkeypatch.setattr(httpx.AsyncClient, "stream",
                        lambda self, method, url, headers=None, json=None: _FakeStream(lines))

    events = [ev async for ev in llm.chat_with_tools_stream(
        messages=[{"role": "user", "content": "hi"}], tools=[])]
    reasoning = [e for e in events if e["type"] == "reasoning_delta"]
    assert reasoning and reasoning[0]["delta"] == "let me think"
    # reasoning still also lands on the terminal done event (for the trace)
    done = [e for e in events if e["type"] == "done"][0]
    assert done["reasoning"] == "let me think"
    # content still streams as before
    content = "".join(e["delta"] for e in events if e["type"] == "content_delta")
    assert content == "answer"
