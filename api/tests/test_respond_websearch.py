import app.chat.respond as respond


def test_registry_has_web_search_when_enabled(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    names = [t["function"]["name"] for t in respond._build_registry("neutral").schemas()]
    assert "web_search" in names
    assert "recall_memory" in names


def test_registry_advertises_web_search_even_when_unconfigured(monkeypatch):
    # Capability is decoupled from credentials: the tool is always offered to the
    # model; execution fails gracefully when no provider/key is configured.
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    names = [t["function"]["name"] for t in respond._build_registry("neutral").schemas()]
    assert "web_search" in names
    assert "recall_memory" in names


def test_max_hops_raised_when_web_search_configured(monkeypatch):
    for k in ("WEB_SEARCH_PROVIDER", "TAVILY_API_KEY",
              "VELLUM_RECALL_MAX_HOPS", "WEB_SEARCH_MAX_HOPS"):
        monkeypatch.delenv(k, raising=False)
    base = respond._max_hops()           # recall-only default (3)
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    assert respond._max_hops() == 4      # web default lifts the ceiling
    assert respond._max_hops() >= base
