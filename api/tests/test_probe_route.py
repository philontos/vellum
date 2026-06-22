"""Probe panel route: a read-only recall inspector. Given a query it returns the
scored retrieval breakdown (kept hits + below-threshold near-misses + snippets)
and the always-in-context durable facts board — without persisting anything."""
from fastapi.testclient import TestClient


def _seed_offer_embed(monkeypatch):
    from app.chat import retrieval

    async def fake_embed(text):
        return [1.0, 0.0, 0.0] if "offer" in text else [0.0, 0.0, 1.0]

    monkeypatch.setattr(retrieval, "embed", fake_embed)


def test_probe_returns_retrieval_and_facts(migrated_db, monkeypatch):
    _seed_offer_embed(monkeypatch)
    from app.store import memory, model
    from app.store.vectors import VectorStore
    u = memory.append_message("user", "should I take the offer")
    VectorStore().add(memory.add_vector_ref("message", u["id"]), [1.0, 0.0, 0.0])
    model.add_fact("has two daughters")

    from app.main import app
    c = TestClient(app)
    before = memory.recent_tail(50)
    body = c.get("/inspect/probe", params={"q": "the offer"}).json()
    after = memory.recent_tail(50)

    assert body["query"] == "the offer"
    assert any(h["kept"] and h["ref_type"] == "message" for h in body["hits"])
    assert "offer" in "\n".join(s["text"] for s in body["snippets"])
    assert any(f["text"] == "has two daughters" for f in body["facts"])
    # read-only: probing never persists the query as a new turn
    assert len(after) == len(before)


def test_probe_empty_query_returns_facts_no_retrieval(migrated_db):
    from app.store import model
    model.add_fact("likes hiking")

    from app.main import app
    c = TestClient(app)
    body = c.get("/inspect/probe", params={"q": ""}).json()
    assert body["hits"] == [] and body["snippets"] == []
    assert any(f["text"] == "likes hiking" for f in body["facts"])
