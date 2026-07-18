import pytest

from app.chat import assemble
from app.store import memory, model
from app.store.db import get_conn


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
    assert msgs[-1]["role"] == "user"
    assert msgs[-1]["content"].endswith("\nhello there")   # annotated tail


@pytest.mark.asyncio
async def test_tail_and_recall_are_scoped_to_the_mode_stream(migrated_db, monkeypatch):
    seen = {}
    async def fake_retrieve(q, stream="neutral", **kw):
        seen["stream"] = stream
        return []
    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    memory.append_message("user", "daily message", stream="neutral")
    memory.append_message("user", "counseling message", stream="freud")

    neutral = await assemble.build_messages(persona_name="neutral")
    assert neutral[-1]["content"].endswith("\ndaily message")  # only neutral tail
    assert seen["stream"] == "neutral"                     # recall scoped to the mode

    freud = await assemble.build_messages(persona_name="freud")
    assert freud[-1]["content"].endswith("\ncounseling message")  # only freud tail
    assert seen["stream"] == "freud"


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


def test_trait_summary_frames_schwartz_as_relative_priority(migrated_db):
    model.set_trait("schwartz", {
        "self_direction": {
            "priority": 0.31, "confidence": 0.7, "stance": "support",
            "status": "core_priority",
        },
        "security": {
            "priority": -0.22, "confidence": 0.6, "stance": "yielding",
            "status": "relative_yielding",
        },
        "tradition": {
            "priority": None, "confidence": 0, "stance": "unobserved",
            "status": "unobserved",
        },
    }, sample_count=5)

    out = assemble._trait_summary()

    assert "0=personal mean" in out
    assert "Self-Direction: above own average (+0.31)" in out
    assert "Security: below own average (-0.22; relative, not rejection)" in out
    assert "Tradition" not in out


def test_trait_summary_centers_legacy_schwartz_during_upgrade(migrated_db):
    model.set_trait("schwartz", {
        "achievement": {"score": 78, "confidence": 0.7},
        "security": {"score": 76, "confidence": 0.7},
        "conformity": {"score": 61, "confidence": 0.4},
    }, sample_count=41)

    out = assemble._trait_summary()

    assert "relative priorities" in out
    assert "Achievement: above own average" in out
    assert "Conformity: below own average" in out


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


@pytest.mark.asyncio
async def test_user_turns_carry_local_time_and_elapsed_context(migrated_db, monkeypatch):
    """The model-facing copy of every user turn gets trusted local-time metadata,
    while assistant text remains untouched. SQLite continues to store raw text."""
    monkeypatch.setenv("VELLUM_TIMEZONE", "Asia/Shanghai")

    async def fake_retrieve(q, **kw):
        return []

    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    first = memory.append_message("user", "first thought")
    reply = memory.append_message("assistant", "go on")
    second = memory.append_message("user", "back to this")
    with get_conn() as conn:
        conn.execute(
            "UPDATE messages SET created_at = ? WHERE id = ?",
            ("2026-07-14 01:15:00", first["id"]),
        )
        conn.execute(
            "UPDATE messages SET created_at = ? WHERE id = ?",
            ("2026-07-14 01:16:00", reply["id"]),
        )
        conn.execute(
            "UPDATE messages SET created_at = ? WHERE id = ?",
            ("2026-07-14 05:45:00", second["id"]),
        )

    msgs = await assemble.build_messages()

    assert "## Time context" in msgs[0]["content"]
    assert "Asia/Shanghai" in msgs[0]["content"]
    assert msgs[1]["content"].startswith(
        '<message_time datetime="2026-07-14T09:15:00+08:00" '
        'timezone="Asia/Shanghai" weekday="Tuesday" period="morning"'
    )
    assert msgs[2] == {"role": "assistant", "content": "go on"}
    assert 'period="afternoon"' in msgs[3]["content"]
    assert 'elapsed_since_previous_user="4h 30m"' in msgs[3]["content"]
    assert msgs[3]["content"].endswith("\nback to this")
    assert memory.get_message(second["id"])["content"] == "back to this"
