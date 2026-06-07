import pytest

from app.model_loop import summary
from app.store import memory
from app.store.vectors import VectorStore


@pytest.mark.asyncio
async def test_summary_stored_embedded_and_indexed(migrated_db, monkeypatch):
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        return {"summary": "discussed whether to take the startup offer; leaning yes"}
    async def fake_embed(text):
        return [1.0, 0.0, 0.0]
    monkeypatch.setattr(summary, "chat_json", fake_chat_json)
    monkeypatch.setattr(summary, "embed", fake_embed)

    memory.append_message("user", "should I take the offer")
    memory.append_message("assistant", "weigh autonomy vs security")
    await summary.run(start_turn=0, end_turn=1)

    # stored summary text
    s = memory.get_summary(1)
    assert s and "startup offer" in s["content"]
    # embedded + indexed + resolvable to a summary
    hit = VectorStore().search_scored([1.0, 0.0, 0.0], k=1)[0]
    ref = memory.resolve_vector_ref(hit[0])
    assert ref["ref_type"] == "summary" and ref["ref_id"] == s["id"]
