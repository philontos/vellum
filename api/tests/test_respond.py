import json
import pytest

import app.chat.respond as respond


async def _fake_stream_no_tool(messages, tools, **kw):
    yield {"type": "content_delta", "delta": "Hello "}
    yield {"type": "content_delta", "delta": "world"}
    yield {"type": "done", "finish_reason": "stop",
           "message": {"role": "assistant", "content": "Hello world"},
           "usage": {"prompt_tokens": 12, "completion_tokens": 3}, "duration_ms": 50,
           "reasoning": "I should greet."}


async def _fake_stream_no_usage(messages, tools, **kw):
    # Provider that doesn't report usage at all (empty usage dict).
    yield {"type": "content_delta", "delta": "Hi"}
    yield {"type": "done", "finish_reason": "stop",
           "message": {"role": "assistant", "content": "Hi"},
           "usage": {}, "duration_ms": 7}


async def _fake_stream_with_tool(messages, tools, **kw):
    # First round: call recall_memory; second round (after tool result): answer.
    if not any(m.get("role") == "tool" for m in messages):
        msg = {"role": "assistant", "content": None,
               "tool_calls": [{"id": "c1", "type": "function",
                               "function": {"name": "recall_memory",
                                            "arguments": json.dumps({"query": "offer"})}}]}
        yield {"type": "done", "finish_reason": "tool_calls", "message": msg,
               "usage": {"prompt_tokens": 10, "completion_tokens": 5}, "duration_ms": 40,
               "reasoning": "need to recall"}
    else:
        yield {"type": "content_delta", "delta": "Per your past: "}
        yield {"type": "content_delta", "delta": "go for it"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "Per your past: go for it"},
               "usage": {"prompt_tokens": 20, "completion_tokens": 8}, "duration_ms": 60,
               "reasoning": "now I can answer"}


@pytest.mark.asyncio
async def test_stream_plain(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_stream_no_tool)
    deltas, final = [], {}
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "final":
            final = ev
    assert "".join(deltas) == "Hello world"
    assert final["content"] == "Hello world"
    # usage + latency surface on the final event (single hop)
    assert final["prompt_tokens"] == 12
    assert final["completion_tokens"] == 3
    assert final["duration_ms"] == 50
    assert final["reasoning"] == "I should greet."


@pytest.mark.asyncio
async def test_final_usage_none_when_provider_omits(monkeypatch):
    # Empty usage → None (renders as `?`), but measured duration still surfaces.
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_stream_no_usage)
    final = {}
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "final":
            final = ev
    assert final["prompt_tokens"] is None
    assert final["completion_tokens"] is None
    assert final["duration_ms"] == 7


@pytest.mark.asyncio
async def test_tool_loop_runs_handler_and_continues(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_stream_with_tool)
    monkeypatch.setattr(respond, "_build_registry",
                        lambda: _stub_registry(monkeypatch))
    out, final = [], {}
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "delta":
            out.append(ev["text"])
        elif ev["type"] == "final":
            final = ev
    assert "go for it" in "".join(out)
    # usage + latency are SUMMED across both tool-loop hops
    assert final["prompt_tokens"] == 30        # 10 + 20
    assert final["completion_tokens"] == 13    # 5 + 8
    assert final["duration_ms"] == 100         # 40 + 60
    # reasoning from every hop is concatenated
    assert final["reasoning"] == "need to recall\n\nnow I can answer"


@pytest.mark.asyncio
async def test_stream_degrades_to_a_only_without_tools(monkeypatch):
    # When the model returns no tool_calls (finish_reason="stop"), the loop
    # exits after the first hop — realistic A-only path, no provider flag needed.
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
