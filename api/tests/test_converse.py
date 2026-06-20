"""converse.reply is the non-streaming entry to vellum's brain used by the
Feishu adapter: same pipeline as POST /chat (persist user, assemble, tool-loop,
persist assistant) but collected into a string instead of streamed."""


def _stub_brain(monkeypatch):
    import app.chat.ingest as ingest
    import app.chat.retrieval as retrieval
    import app.chat.respond as respond

    async def _fake_embed(text):
        return [1.0, 0.0, 0.0]

    monkeypatch.setattr(ingest, "embed", _fake_embed)
    monkeypatch.setattr(retrieval, "embed", _fake_embed)

    async def fake_stream(messages, tools, **kw):
        yield {"type": "content_delta", "delta": "hi "}
        yield {"type": "content_delta", "delta": "there"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "hi there"},
               "usage": {"prompt_tokens": 7, "completion_tokens": 5}, "duration_ms": 42}

    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", fake_stream)


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
