import json
import pytest

import app.chat.respond as respond


async def _fake_stream_no_tool(messages, tools, **kw):
    yield {"type": "content_delta", "delta": "Hello "}
    yield {"type": "content_delta", "delta": "world"}
    yield {"type": "done", "finish_reason": "stop",
           "message": {"role": "assistant", "content": "Hello world"},
           "usage": {}, "duration_ms": 1}


async def _fake_stream_with_tool(messages, tools, **kw):
    # First round: call recall_memory; second round (after tool result): answer.
    if not any(m.get("role") == "tool" for m in messages):
        msg = {"role": "assistant", "content": None,
               "tool_calls": [{"id": "c1", "type": "function",
                               "function": {"name": "recall_memory",
                                            "arguments": json.dumps({"query": "offer"})}}]}
        yield {"type": "done", "finish_reason": "tool_calls", "message": msg,
               "usage": {}, "duration_ms": 1}
    else:
        yield {"type": "content_delta", "delta": "Per your past: "}
        yield {"type": "content_delta", "delta": "go for it"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "Per your past: go for it"},
               "usage": {}, "duration_ms": 1}


@pytest.mark.asyncio
async def test_stream_plain(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_stream_no_tool)
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: True)
    deltas, final = [], {}
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "final":
            final = ev
    assert "".join(deltas) == "Hello world"
    assert final["content"] == "Hello world"


@pytest.mark.asyncio
async def test_tool_loop_runs_handler_and_continues(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_stream_with_tool)
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: True)
    monkeypatch.setattr(respond, "_build_registry",
                        lambda: _stub_registry(monkeypatch))
    out = []
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "delta":
            out.append(ev["text"])
    assert "go for it" in "".join(out)


@pytest.mark.asyncio
async def test_stream_degrades_to_a_only_without_tools(monkeypatch):
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: False)
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_stream_no_tool)
    evs = [ev async for ev in respond.stream([{"role": "system", "content": "s"}])]
    assert evs[-1]["type"] == "final" and evs[-1]["content"] == "Hello world"


def _stub_registry(monkeypatch):
    from app.chat.tools import registry
    reg = registry.ToolRegistry()
    reg.register(
        schema={"type": "function", "function": {"name": "recall_memory",
                "description": "d", "parameters": {"type": "object", "properties": {}}}},
        handler=lambda args: "RECALLED CONTEXT",
    )
    return reg
