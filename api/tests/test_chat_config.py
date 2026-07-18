from app import config


def test_defaults(monkeypatch):
    for k in ("VELLUM_TAIL_SIZE", "VELLUM_RECALL_K", "VELLUM_RECALL_MIN_SIM",
              "VELLUM_NEIGHBORHOOD_W", "VELLUM_RECALL_MAX_HOPS", "VELLUM_PERSONA",
              "VELLUM_TIMEZONE"):
        monkeypatch.delenv(k, raising=False)
    assert config.tail_size() == 20
    assert config.recall_k() == 6
    assert 0.0 < config.recall_min_sim() < 1.0
    assert config.neighborhood_w() == 3
    assert config.recall_max_hops() == 3
    assert config.persona_name() == "neutral"
    assert config.timezone_name() == "Asia/Shanghai"


def test_env_override(monkeypatch):
    monkeypatch.setenv("VELLUM_TAIL_SIZE", "8")
    monkeypatch.setenv("VELLUM_TIMEZONE", "America/New_York")
    assert config.tail_size() == 8
    assert config.timezone_name() == "America/New_York"


def test_inquiry_and_response_limits_cannot_become_unbounded_from_negative_values(
    monkeypatch,
):
    monkeypatch.setenv("VELLUM_RESPONSE_TAIL_SIZE", "-1")
    monkeypatch.setenv("VELLUM_INQUIRY_TAIL_SIZE", "-1")
    monkeypatch.setenv("VELLUM_INQUIRY_EVIDENCE_LIMIT", "-1")
    monkeypatch.setenv("VELLUM_INQUIRY_CONTEXT_TOKENS", "-1")

    assert config.response_tail_size() == 1
    assert config.inquiry_tail_size() == 0
    assert config.inquiry_evidence_limit() == 0
    assert config.inquiry_context_tokens() == 256
