from app.chat import persona


def test_loads_neutral_by_default(monkeypatch):
    monkeypatch.delenv("VELLUM_PERSONA", raising=False)
    p = persona.load()
    assert p.name == "neutral"
    assert "general assistant" in p.voice


def test_unknown_persona_falls_back_to_neutral(monkeypatch):
    monkeypatch.setenv("VELLUM_PERSONA", "does-not-exist")
    assert "general assistant" in persona.load().voice


def test_explicit_name_overrides_env(monkeypatch):
    monkeypatch.setenv("VELLUM_PERSONA", "neutral")
    assert persona.load("freud").name == "freud"


def test_neutral_has_no_overrides():
    # No stance.txt / trait_frame.txt → the default framings apply (see assemble.py).
    p = persona.load("neutral")
    assert p.stance is None
    assert p.trait_frame is None


def test_freud_carries_its_own_voice_stance_and_trait_frame():
    p = persona.load("freud")
    assert "psychoanalyst" in p.voice.lower()
    assert p.stance is not None and "interpret" in p.stance.lower()
    assert p.trait_frame is not None and "never name a trait" in p.trait_frame.lower()


def test_available_lists_known_modes():
    assert {"neutral", "freud"} <= persona.available()
