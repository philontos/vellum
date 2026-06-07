from app import config


def test_defaults(monkeypatch):
    for k in ("VELLUM_TAIL_SIZE", "VELLUM_RECALL_K", "VELLUM_RECALL_MIN_SIM",
              "VELLUM_NEIGHBORHOOD_W", "VELLUM_RECALL_MAX_HOPS", "VELLUM_PERSONA"):
        monkeypatch.delenv(k, raising=False)
    assert config.tail_size() == 20
    assert config.recall_k() == 6
    assert 0.0 < config.recall_min_sim() < 1.0
    assert config.neighborhood_w() == 3
    assert config.recall_max_hops() == 3
    assert config.persona_name() == "neutral"


def test_env_override(monkeypatch):
    monkeypatch.setenv("VELLUM_TAIL_SIZE", "8")
    assert config.tail_size() == 8
