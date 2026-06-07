import pytest

from app.chat import assemble
from app.store import memory, model


@pytest.mark.asyncio
async def test_build_messages_has_altitude_persona_and_tail(migrated_db, monkeypatch):
    async def fake_retrieve(q, **kw):
        return []
    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    model.set_dossier("values autonomy")
    model.add_fact("allergic to penicillin")
    memory.append_message("user", "hello there")
    msgs = await assemble.build_messages()
    system = msgs[0]["content"]
    assert msgs[0]["role"] == "system"
    assert "general assistant" in system            # persona
    assert "background reference" in system.lower()  # altitude framing
    assert "values autonomy" in system               # dossier
    assert "allergic to penicillin" in system        # facts
    assert msgs[-1] == {"role": "user", "content": "hello there"}   # tail tail


@pytest.mark.asyncio
async def test_retrieved_snippets_included(migrated_db, monkeypatch):
    async def fake_retrieve(q, **kw):
        return [{"start": 0, "end": 1, "text": "user: x\nassistant: y"}]
    monkeypatch.setattr(
        assemble.retrieval, "retrieve",
        fake_retrieve,
    )
    memory.append_message("user", "q")
    system = (await assemble.build_messages())[0]["content"]
    assert "assistant: y" in system
