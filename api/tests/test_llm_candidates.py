import asyncio

import pytest

from app.llm import candidates
from app.llm import client as llm


def test_candidate_catalog_has_primary_glm_and_kimi_without_exposing_secrets(
    monkeypatch,
):
    monkeypatch.setenv("LLM_BASE_URL", "https://primary.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "primary-secret")
    monkeypatch.setenv("LLM_MODEL", "primary-model")
    monkeypatch.setenv("GLM_API_KEY", "glm-secret")
    monkeypatch.setenv("KIMI_API_KEY", "kimi-secret")

    catalog = candidates.public_candidates()

    assert catalog == [
        {
            "id": "primary",
            "name": "Primary model",
            "model": "primary-model",
            "configured": True,
        },
        {
            "id": "glm",
            "name": "GLM",
            "model": "glm-5.2",
            "configured": True,
        },
        {
            "id": "kimi",
            "name": "Kimi K3",
            "model": "kimi-k3",
            "configured": True,
        },
    ]
    assert "primary-secret" not in repr(catalog)
    assert "glm-secret" not in repr(catalog)
    assert "kimi-secret" not in repr(catalog)


def test_candidate_provider_defaults_are_overridable(monkeypatch):
    monkeypatch.setenv("GLM_BASE_URL", "https://glm-proxy.test/v1")
    monkeypatch.setenv("GLM_API_KEY", "g")
    monkeypatch.setenv("GLM_MODEL", "glm-custom")
    monkeypatch.setenv("MOONSHOT_API_KEY", "m")

    assert candidates.resolve("glm") == {
        "base_url": "https://glm-proxy.test/v1",
        "api_key": "g",
        "model": "glm-custom",
    }
    assert candidates.resolve("kimi") == {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "m",
        "model": "kimi-k3",
    }


def test_formal_llm_pipeline_selects_a_named_candidate(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://primary.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "primary")
    monkeypatch.setenv("LLM_MODEL", "primary-model")
    monkeypatch.setenv("GLM_API_KEY", "glm-key")
    monkeypatch.setenv("KIMI_API_KEY", "kimi-key")

    monkeypatch.setenv("LLM_CANDIDATE", "glm")
    assert llm.resolve_structured_llm_config() == {
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "glm-key",
        "model": "glm-5.2",
    }

    monkeypatch.setenv("LLM_CANDIDATE", "kimi")
    assert llm.resolve_structured_llm_config() == {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "kimi-key",
        "model": "kimi-k3",
    }


def test_eval_request_override_wins_over_formal_candidate(monkeypatch):
    monkeypatch.setenv("LLM_CANDIDATE", "glm")
    monkeypatch.setenv("GLM_API_KEY", "glm-key")
    override = {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "kimi-key",
        "model": "kimi-k3",
    }

    with llm.use_llm_config(override):
        assert llm.resolve_structured_llm_config() == override

    assert llm.resolve_structured_llm_config()["model"] == "glm-5.2"


def test_primary_integration_stays_distinct_from_the_formal_selection(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://primary.test/v1")
    monkeypatch.setenv("LLM_API_KEY", "primary-key")
    monkeypatch.setenv("LLM_MODEL", "primary-model")
    monkeypatch.setenv("LLM_CANDIDATE", "kimi")
    monkeypatch.setenv("KIMI_API_KEY", "kimi-key")

    assert candidates.resolve("primary")["model"] == "primary-model"
    assert candidates.resolve_for_scenario("chat")["model"] == "kimi-k3"
    assert candidates.public_candidates()[0] == {
        "id": "primary",
        "name": "Primary model",
        "model": "primary-model",
        "configured": True,
    }


def test_llm_stages_map_to_their_configured_scenarios(monkeypatch):
    seen = []

    def resolve(scenario: str) -> dict[str, str]:
        seen.append(scenario)
        return {
            "base_url": f"https://{scenario}.test/v1",
            "api_key": f"{scenario}-key",
            "model": f"{scenario}-model",
        }

    monkeypatch.setattr(candidates, "resolve_for_scenario", resolve)

    assert llm.resolve_structured_llm_config()["model"] == "chat-model"
    assert llm.resolve_structured_llm_config(stage="chat")["model"] == "chat-model"
    assert llm.resolve_structured_llm_config(stage="summary")["model"] == (
        "background-model"
    )
    assert llm.resolve_structured_llm_config(stage="trait")["model"] == (
        "background-model"
    )
    assert llm.resolve_structured_llm_config(stage="eval")["model"] == (
        "evaluation-model"
    )
    assert llm.resolve_structured_llm_config(stage="evaluation")["model"] == (
        "evaluation-model"
    )
    assert seen == [
        "chat", "chat", "background", "background", "evaluation", "evaluation",
    ]


@pytest.mark.asyncio
async def test_candidate_overrides_are_isolated_between_concurrent_runs():
    async def selected(model: str) -> str:
        config = {
            "base_url": f"https://{model}.test/v1",
            "api_key": f"{model}-key",
            "model": model,
        }
        with llm.use_llm_config(config):
            await asyncio.sleep(0)
            return llm.resolve_structured_llm_config()["model"]

    assert await asyncio.gather(selected("glm-5.2"), selected("kimi-k3")) == [
        "glm-5.2", "kimi-k3",
    ]
