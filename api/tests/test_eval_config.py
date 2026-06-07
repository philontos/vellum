import pytest

from evals import config as ec


def _set_gen(monkeypatch, model, base="https://eval.test/v1", key="k"):
    monkeypatch.setenv("EVAL_GEN_BASE_URL", base)
    monkeypatch.setenv("EVAL_GEN_API_KEY", key)
    monkeypatch.setenv("EVAL_GEN_MODEL", model)


def test_resolves_eval_gen(monkeypatch):
    _set_gen(monkeypatch, "judge-model")
    cfg = ec.eval_gen_config()
    assert cfg["model"] == "judge-model" and cfg["base_url"] == "https://eval.test/v1"


def test_require_eval_gen_ok_when_configured(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "system-model")
    _set_gen(monkeypatch, "judge-model")
    ec.require_eval_gen()   # different models → no raise, no warning


def test_same_model_allowed_but_warns(monkeypatch, capsys):
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    _set_gen(monkeypatch, "deepseek-chat")
    ec.require_eval_gen()   # same model is now ALLOWED (no raise)
    assert "grading itself" in capsys.readouterr().err


def test_require_eval_gen_raises_when_unconfigured(monkeypatch):
    monkeypatch.delenv("EVAL_GEN_MODEL", raising=False)
    monkeypatch.delenv("EVAL_GEN_BASE_URL", raising=False)
    monkeypatch.delenv("EVAL_GEN_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not configured"):
        ec.require_eval_gen()
