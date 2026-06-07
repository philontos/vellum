import asyncio

from fastapi.testclient import TestClient


def test_chat_triggers_background_modeling(migrated_db, monkeypatch):
    # stub embed + model stream (reuse the chat-route style)
    import app.chat.ingest as ingest
    import app.chat.retrieval as retrieval
    import app.chat.respond as respond
    import app.routes.chat as chat_route

    async def fake_embed(t): return [1.0, 0.0, 0.0]
    monkeypatch.setattr(ingest, "embed", fake_embed)
    monkeypatch.setattr(retrieval, "embed", fake_embed)
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: True)

    async def fake_stream(messages, tools, **kw):
        yield {"type": "content_delta", "delta": "ok"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "ok"}, "usage": {}, "duration_ms": 1}
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", fake_stream)

    ran = {"called": False}
    async def fake_run_pending():
        ran["called"] = True
    monkeypatch.setattr(chat_route.runner, "run_pending", fake_run_pending)

    from app.main import app
    client = TestClient(app)
    with client.stream("POST", "/chat", json={"message": "hi"}) as r:
        "".join(r.iter_text())
    # give the scheduled background task a tick to run
    assert ran["called"] is True
