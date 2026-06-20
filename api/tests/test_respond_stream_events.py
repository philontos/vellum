import json

import pytest

import app.chat.respond as respond
from app.chat.tools import registry


async def _fake_reason_tool_answer(messages, tools, **kw):
    """Hop 1: stream reasoning, then call web_search. Hop 2: stream the answer."""
    if not any(m.get("role") == "tool" for m in messages):
        yield {"type": "reasoning_delta", "delta": "I should look this up. "}
        msg = {"role": "assistant", "content": None,
               "tool_calls": [{"id": "c1", "type": "function",
                               "function": {"name": "web_search",
                                            "arguments": json.dumps({"query": "X latest"})}}]}
        yield {"type": "done", "finish_reason": "tool_calls", "message": msg,
               "usage": {}, "duration_ms": 1}
    else:
        yield {"type": "content_delta", "delta": "Here it is."}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "Here it is."},
               "usage": {}, "duration_ms": 1}


def _registry(handler):
    reg = registry.ToolRegistry()
    reg.register(
        schema={"type": "function", "function": {"name": "web_search", "description": "d",
                "parameters": {"type": "object", "properties": {}}}},
        handler=handler,
    )
    return reg


@pytest.mark.asyncio
async def test_stream_emits_reasoning_events(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_reason_tool_answer)
    monkeypatch.setattr(respond, "_build_registry", lambda: _registry(lambda a: "[1] R\nhttp://x\nb"))
    reasoning = []
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "reasoning":
            reasoning.append(ev["text"])
    assert "".join(reasoning) == "I should look this up. "


@pytest.mark.asyncio
async def test_stream_emits_tool_start_and_end(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_reason_tool_answer)
    monkeypatch.setattr(respond, "_build_registry", lambda: _registry(lambda a: "[1] R\nhttp://x\nb"))
    starts, ends = [], []
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "tool_start":
            starts.append(ev)
        elif ev["type"] == "tool_end":
            ends.append(ev)
    assert len(starts) == 1
    assert starts[0]["name"] == "web_search" and starts[0]["query"] == "X latest"
    assert len(ends) == 1
    assert ends[0]["name"] == "web_search" and ends[0]["ok"] is True


@pytest.mark.asyncio
async def test_tool_end_flags_error_result(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_reason_tool_answer)
    monkeypatch.setattr(respond, "_build_registry",
                        lambda: _registry(lambda a: "ERROR running web_search: boom"))
    ends = [ev async for ev in respond.stream([{"role": "system", "content": "s"}])
            if ev["type"] == "tool_end"]
    assert ends and ends[0]["ok"] is False


@pytest.mark.asyncio
async def test_final_answer_still_streams(monkeypatch):
    # New process events must not disturb the existing delta/final contract.
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_reason_tool_answer)
    monkeypatch.setattr(respond, "_build_registry", lambda: _registry(lambda a: "[1] R\nhttp://x\nb"))
    deltas, final = [], {}
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "final":
            final = ev
    assert "".join(deltas) == "Here it is."
    assert final["content"] == "Here it is."
