from app.llm import client as llm


def test_known_provider_tool_capability(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert llm.provider_supports_tools() is True


def test_unknown_provider_defaults_true(monkeypatch):
    # Custom base_url, no preset → optimistic default (we degrade at runtime if it 400s)
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    assert llm.provider_supports_tools() is True
