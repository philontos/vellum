from app.chat import persona


def test_loads_neutral_by_default(monkeypatch):
    monkeypatch.delenv("VELLUM_PERSONA", raising=False)
    text = persona.load()
    assert "general assistant" in text


def test_unknown_persona_falls_back_to_neutral(monkeypatch):
    monkeypatch.setenv("VELLUM_PERSONA", "does-not-exist")
    assert "general assistant" in persona.load()
