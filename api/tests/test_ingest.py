import pytest

import app.chat.ingest as ingest
from app.store import memory
from app.store.vectors import VectorStore


@pytest.mark.asyncio
async def test_persist_user_stores_and_embeds(migrated_db, monkeypatch):
    async def _fake_embed(text):
        return [1.0, 0.0, 0.0]
    monkeypatch.setattr(ingest, "embed", _fake_embed)
    res = await ingest.persist_user("hello")
    assert res["turn"] == 0
    # message stored
    assert memory.recent_tail(1)[0]["content"] == "hello"
    # vector indexed + resolvable back to the message
    hits = VectorStore().search_scored([1.0, 0.0, 0.0], k=1)
    ref = memory.resolve_vector_ref(hits[0][0])
    assert ref["ref_type"] == "message" and ref["ref_id"] == res["id"]


@pytest.mark.asyncio
async def test_persist_assistant_stores_no_vector(migrated_db, monkeypatch):
    async def _fake_embed(text):
        return [1.0, 0.0, 0.0]
    monkeypatch.setattr(ingest, "embed", _fake_embed)
    await ingest.persist_user("hi")                 # creates the index (dim=3)
    ingest.persist_assistant("hello back")
    assert memory.recent_tail(1)[0]["role"] == "assistant"
    # only the user vector exists
    assert VectorStore().index.get_current_count() == 1
