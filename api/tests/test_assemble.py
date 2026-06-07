from app.chat import assemble
from app.store import memory, model


def test_build_messages_has_altitude_persona_and_tail(migrated_db, monkeypatch):
    monkeypatch.setattr(assemble.retrieval, "retrieve", lambda q, **kw: [])
    model.set_dossier("values autonomy")
    model.add_fact("allergic to penicillin")
    memory.append_message("user", "hello there")
    msgs = assemble.build_messages()
    system = msgs[0]["content"]
    assert msgs[0]["role"] == "system"
    assert "general assistant" in system            # persona
    assert "background reference" in system.lower()  # altitude framing
    assert "values autonomy" in system               # dossier
    assert "allergic to penicillin" in system        # facts
    assert msgs[-1] == {"role": "user", "content": "hello there"}   # tail tail


def test_retrieved_snippets_included(migrated_db, monkeypatch):
    monkeypatch.setattr(
        assemble.retrieval, "retrieve",
        lambda q, **kw: [{"start": 0, "end": 1, "text": "user: x\nassistant: y"}],
    )
    memory.append_message("user", "q")
    system = assemble.build_messages()[0]["content"]
    assert "assistant: y" in system
