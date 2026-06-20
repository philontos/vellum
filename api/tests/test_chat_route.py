import json

from fastapi.testclient import TestClient


def _setup(monkeypatch):
    # avoid network: stub embed + the model stream
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
               "usage": {"prompt_tokens": 7, "completion_tokens": 5}, "duration_ms": 42,
               "reasoning": "greet the user"}
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", fake_stream)


def test_chat_streams_and_persists_both_turns(migrated_db, monkeypatch):
    _setup(monkeypatch)
    from app.main import app
    from app.store import memory
    from app.store.traces import get_conn

    client = TestClient(app)
    with client.stream("POST", "/chat", json={"message": "hello"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "hi " in body and "there" in body       # streamed content reached client

    tail = memory.recent_tail(2)
    assert tail[0]["role"] == "user" and tail[0]["content"] == "hello"
    assert tail[1]["role"] == "assistant" and tail[1]["content"] == "hi there"

    with get_conn() as conn:
        row = conn.execute(
            "SELECT prompt_tokens, completion_tokens, duration_ms, reasoning "
            "FROM traces WHERE stage='chat'"
        ).fetchall()
    assert len(row) == 1                           # one chat trace recorded
    # token counts + latency are recorded, not None (the `?→? tok · ?ms` bug)
    assert row[0]["prompt_tokens"] == 7
    assert row[0]["completion_tokens"] == 5
    assert row[0]["duration_ms"] == 42
    assert row[0]["reasoning"] == "greet the user"  # reasoning captured


def test_chat_trace_is_tagged_with_the_assistant_turn(migrated_db, monkeypatch):
    """The chat trace must carry the round's turn (the assistant message's turn)
    so the Traces panel can group a round's chat with the facts/etc it triggered.
    Background traces are already stamped with that same max_turn."""
    _setup(monkeypatch)
    from app.main import app
    from app.store import memory
    from app.store.traces import get_conn

    client = TestClient(app)
    with client.stream("POST", "/chat", json={"message": "hello"}) as r:
        assert r.status_code == 200
        "".join(r.iter_text())

    assistant_turn = memory.recent_tail(1)[0]["turn"]
    with get_conn() as conn:
        rows = conn.execute("SELECT turn FROM traces WHERE stage='chat'").fetchall()
    assert len(rows) == 1
    assert rows[0]["turn"] == assistant_turn       # not None — anchored to the round


def test_chat_stream_emits_error_frame_and_done_when_model_fails(migrated_db, monkeypatch):
    """If the model stream blows up mid-flight, the client must still get an
    error frame AND the [DONE] sentinel — otherwise the UI spins forever."""
    _setup(monkeypatch)
    import app.chat.respond as respond

    async def boom_stream(messages, tools, **kw):
        yield {"type": "content_delta", "delta": "partial "}
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", boom_stream)

    from app.main import app
    client = TestClient(app, raise_server_exceptions=False)
    with client.stream("POST", "/chat", json={"message": "hello"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())

    assert "partial " in body                 # the delta sent before the failure
    assert '"error"' in body                  # failure surfaced as an SSE frame
    assert "provider exploded" in body
    assert body.strip().endswith("[DONE]")    # stream is always terminated
