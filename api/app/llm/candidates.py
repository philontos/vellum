"""Named model integrations and scenario-specific production selection.

Credentials come from owner-managed SQLite rows or environment fallbacks. The
evaluation catalog deliberately contains only display metadata and readiness,
so the browser never receives a base URL or API key from that public endpoint.
"""
import os
from dataclasses import dataclass


class ModelCandidateError(ValueError):
    pass


@dataclass(frozen=True)
class _CandidateSpec:
    id: str
    name: str
    base_url_env: str
    api_key_envs: tuple[str, ...]
    model_env: str
    default_base_url: str
    default_model: str


_SPECS = (
    _CandidateSpec(
        id="primary",
        name="Primary model",
        base_url_env="LLM_BASE_URL",
        api_key_envs=("LLM_API_KEY",),
        model_env="LLM_MODEL",
        default_base_url="",
        default_model="",
    ),
    _CandidateSpec(
        id="glm",
        name="GLM",
        base_url_env="GLM_BASE_URL",
        api_key_envs=("GLM_API_KEY",),
        model_env="GLM_MODEL",
        default_base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-5.2",
    ),
    _CandidateSpec(
        id="kimi",
        name="Kimi K3",
        base_url_env="KIMI_BASE_URL",
        api_key_envs=("KIMI_API_KEY", "MOONSHOT_API_KEY"),
        model_env="KIMI_MODEL",
        default_base_url="https://api.moonshot.cn/v1",
        default_model="kimi-k3",
    ),
)
_BY_ID = {spec.id: spec for spec in _SPECS}
_MANAGEABLE_IDS = tuple(spec.id for spec in _SPECS)
MODEL_SCENARIOS = ("chat", "inquiry", "background", "evaluation")


def _first_env(names: tuple[str, ...]) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _environment_config(spec: _CandidateSpec) -> dict[str, str]:
    return {
        "base_url": (
            os.getenv(spec.base_url_env) or spec.default_base_url
        ).strip().rstrip("/"),
        "api_key": _first_env(spec.api_key_envs),
        "model": (
            os.getenv(spec.model_env) or spec.default_model
        ).strip(),
    }


def _config(spec: _CandidateSpec) -> dict[str, str]:
    from app.llm import candidate_store

    stored = candidate_store.get_config(spec.id)
    if stored is not None:
        return {
            "base_url": stored["base_url"],
            "api_key": stored["api_key"],
            "model": stored["model"],
        }
    return _environment_config(spec)


def _configured(config: dict[str, str]) -> bool:
    return bool(config["base_url"] and config["api_key"] and config["model"])


def public_candidates() -> list[dict]:
    """Return safe model metadata in stable UI order."""
    result = []
    for spec in _SPECS:
        config = _config(spec)
        result.append({
            "id": spec.id,
            "name": spec.name,
            "model": config["model"],
            "configured": _configured(config),
        })
    return result


def manageable_candidates() -> list[dict[str, str]]:
    """Safe definitions for the owner-managed candidate workspace."""
    return [
        {
            "id": spec.id,
            "name": spec.name,
            "default_base_url": spec.default_base_url,
            "default_model": spec.default_model,
        }
        for spec in _SPECS
        if spec.id in _MANAGEABLE_IDS
    ]


def environment_config(candidate_id: str) -> dict[str, str]:
    """Resolve only environment/default values, bypassing owner-managed state."""
    spec = _BY_ID.get((candidate_id or "").strip().lower())
    if spec is None or spec.id not in _MANAGEABLE_IDS:
        raise ModelCandidateError(f"Unknown configurable model candidate {candidate_id!r}")
    return _environment_config(spec)


def _selected_fallback() -> str:
    selected = (os.getenv("LLM_CANDIDATE") or "").strip().lower() or "primary"
    if selected not in _BY_ID:
        choices = ", ".join(item.id for item in _SPECS)
        raise ModelCandidateError(
            f"Unknown production model candidate {selected!r}; choose from {choices}"
        )
    return selected


def route_for_scenario(scenario: str) -> dict[str, str]:
    """Return the saved route or the legacy deployment-wide fallback."""
    normalized = (scenario or "").strip().lower()
    if normalized not in MODEL_SCENARIOS:
        choices = ", ".join(MODEL_SCENARIOS)
        raise ModelCandidateError(
            f"Unknown model scenario {scenario!r}; choose from {choices}"
        )
    from app.llm import candidate_store

    stored = candidate_store.get_route(normalized)
    if stored is not None:
        return {
            "scenario": normalized,
            "candidate_id": stored["candidate_id"],
            "source": "stored",
        }
    if normalized == "inquiry":
        inherited = candidate_store.get_route("chat")
        if inherited is not None:
            return {
                "scenario": normalized,
                "candidate_id": inherited["candidate_id"],
                "source": "inherited",
            }
    return {
        "scenario": normalized,
        "candidate_id": _selected_fallback(),
        "source": "environment",
    }


def resolve_for_scenario(scenario: str) -> dict[str, str]:
    """Resolve the concrete model selected for one production scenario."""
    return resolve(route_for_scenario(scenario)["candidate_id"])


def resolve(candidate_id: str) -> dict[str, str]:
    """Resolve one candidate to a private request config.

    The primary candidate preserves the existing behavior: an incomplete
    deployment reaches the LLM layer and produces its established diagnostic
    error. Named optional candidates fail early with actionable setup guidance.
    """
    spec = _BY_ID.get((candidate_id or "").strip().lower())
    if spec is None:
        choices = ", ".join(item.id for item in _SPECS)
        raise ModelCandidateError(
            f"Unknown model candidate {candidate_id!r}; choose from {choices}"
        )
    config = _config(spec)
    if spec.id != "primary" and not _configured(config):
        keys = " or ".join(spec.api_key_envs)
        raise ModelCandidateError(
            f"{spec.name} candidate is not configured. Set {keys}."
        )
    return config
