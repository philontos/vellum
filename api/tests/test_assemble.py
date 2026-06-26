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
async def test_counseling_persona_swaps_voice_stance_and_trait_frame(migrated_db, monkeypatch):
    async def fake_retrieve(q, **kw):
        return []
    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    model.set_trait("ocean", {"O": {"score": 75}}, sample_count=5)
    memory.append_message("user", "i feel stuck")
    system = (await assemble.build_messages(persona_name="freud"))[0]["content"]
    assert "psychoanalyst" in system.lower()                 # freud voice in play
    assert "evenly-suspended attention" in system.lower()    # freud stance replaced the default altitude
    assert assemble._ALTITUDE not in system                  # default altitude gone for this mode
    assert assemble._TRAIT_FRAME not in system               # default trait frame replaced too
    assert "silent formulation" in system.lower()            # freud's clinical-lens trait frame in its place


def test_trait_summary_renders_named_bands_with_scores(migrated_db):
    model.set_trait("ocean", {
        "O": {"score": 75}, "C": {"score": 71}, "E": {"score": 55},
        "A": {"score": 69}, "N": {"score": 48},
    }, sample_count=10)
    out = assemble._trait_summary()
    assert "Openness" in out          # full sub-dimension name, not bare "O"
    assert "high (75)" in out         # >60 → high, score kept
    assert "moderate (55)" in out     # 40-60 → moderate (Extraversion=55)


def test_trait_summary_bipolar_uses_correct_pole(migrated_db):
    # mbti J_P poles ["J","P"] mean 0=J, 100=P, so 72 leans toward P, NOT J.
    model.set_trait("mbti", {"J_P": {"score": 72}}, sample_count=5)
    out = assemble._trait_summary()
    assert "P (72)" in out
    assert "J (72)" not in out


@pytest.mark.asyncio
async def test_personality_framing_directs_diagnostic_use(migrated_db, monkeypatch):
    async def fake_retrieve(q, **kw):
        return []
    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    model.set_trait("ocean", {"O": {"score": 75}}, sample_count=5)
    memory.append_message("user", "hi")
    system = (await assemble.build_messages())[0]["content"]
    assert "How the user tends to be" in system        # new header
    assert "hypotheses" in system.lower()               # diagnostic frame (unique to trait block)
    assert "reference only" not in system.lower()        # weak framing removed


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
