import pytest

from evals import config as ec


def test_resolves_eval_gen(monkeypatch):
    monkeypatch.setenv("EVAL_GEN_BASE_URL", "https://eval.test/v1")
    monkeypatch.setenv("EVAL_GEN_API_KEY", "k")
    monkeypatch.setenv("EVAL_GEN_MODEL", "judge-model")
    cfg = ec.eval_gen_config()
    assert cfg["model"] == "judge-model" and cfg["base_url"] == "https://eval.test/v1"


def test_enforce_distinct_raises_when_same(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "same-model")
    monkeypatch.setenv("EVAL_GEN_MODEL", "same-model")
    monkeypatch.setenv("EVAL_GEN_API_KEY", "k")
    monkeypatch.setenv("EVAL_GEN_BASE_URL", "https://eval.test/v1")
    with pytest.raises(RuntimeError, match="must differ"):
        ec.enforce_distinct_model()


def test_enforce_distinct_ok_when_different(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "system-model")
    monkeypatch.setenv("EVAL_GEN_MODEL", "judge-model")
    monkeypatch.setenv("EVAL_GEN_API_KEY", "k")
    monkeypatch.setenv("EVAL_GEN_BASE_URL", "https://eval.test/v1")
    ec.enforce_distinct_model()   # must not raise
