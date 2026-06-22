from app import config


def test_web_search_unconfigured_by_default(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_PROVIDER", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert config.web_search_configured() is False


def test_web_search_configured_with_tavily_and_key(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
    assert config.web_search_configured() is True


def test_web_search_unconfigured_when_key_missing(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "tavily")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert config.web_search_configured() is False


def test_web_search_config_defaults(monkeypatch):
    for k in ("WEB_SEARCH_MAX_RESULTS", "WEB_SEARCH_DEPTH", "WEB_SEARCH_MAX_HOPS"):
        monkeypatch.delenv(k, raising=False)
    assert config.web_search_max_results() == 5
    assert config.web_search_depth() == "basic"
    assert config.web_search_max_hops() == 4
