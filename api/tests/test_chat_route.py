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
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: True)

    async def fake_stream(messages, tools, **kw):
        yield {"type": "content_delta", "delta": "hi "}
        yield {"type": "content_delta", "delta": "there"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "hi there"},
               "usage": {}, "duration_ms": 1}
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
        n = conn.execute("SELECT COUNT(*) c FROM traces WHERE stage='chat'").fetchone()["c"]
    assert n == 1                                  # one chat trace recorded
