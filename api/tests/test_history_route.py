from fastapi.testclient import TestClient


def test_history_returns_messages_oldest_first(migrated_db):
    from app.main import app
    from app.store import memory
    memory.append_message("user", "first")
    memory.append_message("assistant", "second")
    memory.append_message("user", "third")

    client = TestClient(app)
    r = client.get("/history?limit=2")
    assert r.status_code == 200
    data = r.json()["messages"]
    assert [m["content"] for m in data] == ["second", "third"]   # last 2, oldest-first
    assert data[0]["role"] == "assistant" and "turn" in data[0]


def test_history_empty(migrated_db):
    from app.main import app
    r = TestClient(app).get("/history")
    assert r.status_code == 200 and r.json()["messages"] == []
