"""converse.reply is the non-streaming entry to vellum's brain used by the
Feishu adapter: same pipeline as POST /chat (persist user, assemble, tool-loop,
persist assistant) but collected into a string instead of streamed."""


def _stub_brain(monkeypatch):
    import app.chat.ingest as ingest
    import app.chat.retrieval as retrieval
    import app.chat.respond as respond
    import app.model_loop.runner as runner

    async def _fake_embed(text):
        return [1.0, 0.0, 0.0]

    monkeypatch.setattr(ingest, "embed", _fake_embed)
    monkeypatch.setattr(retrieval, "embed", _fake_embed)

    async def fake_stream(messages, tools, **kw):
        yield {"type": "content_delta", "delta": "hi "}
        yield {"type": "content_delta", "delta": "there"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "hi there"},
               "usage": {"prompt_tokens": 7, "completion_tokens": 5}, "duration_ms": 42,
               "reasoning": "greet the user"}

    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", fake_stream)

    # Background modeling is fired-and-forgotten by reply(); default it to a
    # no-op so unrelated tests stay quiet (a test that cares overrides it).
    async def _noop_run_pending():
        return None

    monkeypatch.setattr(runner, "run_pending", _noop_run_pending)


async def test_reply_returns_assistant_text(migrated_db, monkeypatch):
    _stub_brain(monkeypatch)
    from app.chat import converse

    answer = await converse.reply("hello")
    assert answer == "hi there"


async def test_reply_persists_both_turns(migrated_db, monkeypatch):
    _stub_brain(monkeypatch)
    from app.chat import converse
    from app.store import memory

    await converse.reply("hello")

    tail = memory.recent_tail(2)
    assert tail[0]["role"] == "user" and tail[0]["content"] == "hello"
    assert tail[1]["role"] == "assistant" and tail[1]["content"] == "hi there"


async def test_reply_records_a_chat_trace(migrated_db, monkeypatch):
    """A Feishu turn must leave the same diagnostic trace as POST /chat: one
    'chat' trace stamped with the round's turn, carrying token counts, latency
    and reasoning (else the Traces panel shows nothing for Feishu chats)."""
    _stub_brain(monkeypatch)
    from app.chat import converse
    from app.store import memory
    from app.store.traces import get_conn

    await converse.reply("hello")

    assistant_turn = memory.recent_tail(1)[0]["turn"]
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT turn, prompt_tokens, completion_tokens, duration_ms, reasoning "
            "FROM traces WHERE stage='chat'"
        ).fetchall()
    assert len(rows) == 1                              # exactly one chat trace
    assert rows[0]["turn"] == assistant_turn           # anchored to the round
    assert rows[0]["prompt_tokens"] == 7
    assert rows[0]["completion_tokens"] == 5
    assert rows[0]["duration_ms"] == 42
    assert rows[0]["reasoning"] == "greet the user"


async def test_reply_records_tool_calls_in_trace(migrated_db, monkeypatch):
    """A Feishu turn that calls a tool must persist the calls (name/args/result/
    ok) on its trace — without this the trace shows no tool activity at all."""
    import json

    import app.chat.respond as respond
    from app.chat import converse
    from app.chat.tools import registry
    from app.store.traces import get_conn

    _stub_brain(monkeypatch)

    async def tool_then_answer(messages, tools, **kw):
        if not any(m.get("role") == "tool" for m in messages):
            msg = {"role": "assistant", "content": None,
                   "tool_calls": [{"id": "c1", "type": "function",
                                   "function": {"name": "web_search",
                                                "arguments": json.dumps({"query": "Q"})}}]}
            yield {"type": "done", "finish_reason": "tool_calls", "message": msg,
                   "usage": {}, "duration_ms": 1}
        else:
            yield {"type": "content_delta", "delta": "answer"}
            yield {"type": "done", "finish_reason": "stop",
                   "message": {"role": "assistant", "content": "answer"},
                   "usage": {}, "duration_ms": 1}

    def _reg(*_a):
        reg = registry.ToolRegistry()
        reg.register(
            schema={"type": "function", "function": {"name": "web_search", "description": "d",
                    "parameters": {"type": "object", "properties": {}}}},
            handler=lambda a: "found it",
        )
        return reg

    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", tool_then_answer)
    monkeypatch.setattr(respond, "_build_registry", _reg)

    await converse.reply("hello")

    with get_conn() as conn:
        row = conn.execute("SELECT tool_calls FROM traces WHERE stage='chat'").fetchone()
    assert json.loads(row["tool_calls"]) == [
        {"name": "web_search", "args": {"query": "Q"}, "result": "found it", "ok": True},
    ]


async def test_reply_triggers_background_modeling(migrated_db, monkeypatch):
    """A Feishu turn must kick off the same background modeling (facts/trait/
    summary/dossier) that POST /chat schedules, so the model keeps learning from
    Feishu conversations too."""
    import asyncio

    import app.model_loop.runner as runner

    _stub_brain(monkeypatch)

    ran = {"called": False}

    async def fake_run_pending():
        ran["called"] = True

    monkeypatch.setattr(runner, "run_pending", fake_run_pending)

    from app.chat import converse

    await converse.reply("hello")
    await asyncio.sleep(0)        # let the fired-and-forgotten task run

    assert ran["called"] is True
