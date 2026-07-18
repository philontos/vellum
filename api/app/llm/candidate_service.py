"""Owner-facing validation and redacted views for model candidates."""
from urllib.parse import urlsplit

import httpx

from app.llm import candidate_store, candidates


VALIDATION_TIMEOUT_SECONDS = 30.0


class CandidateAdminError(ValueError):
    pass


class UnknownCandidateError(CandidateAdminError):
    pass


class UnknownScenarioError(CandidateAdminError):
    pass


class CandidateValidationError(CandidateAdminError):
    pass


def _definition(candidate_id: str) -> dict[str, str]:
    normalized = (candidate_id or "").strip().lower()
    for definition in candidates.manageable_candidates():
        if definition["id"] == normalized:
            return definition
    raise UnknownCandidateError(f"Unknown model candidate {candidate_id!r}")


def _normalize_base_url(value: str) -> str:
    base_url = (value or "").strip().rstrip("/")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise CandidateAdminError(
            "Base URL must be an HTTP(S) URL without credentials, query, or fragment."
        )
    if len(base_url) > 2048:
        raise CandidateAdminError("Base URL is too long.")
    return base_url


def _full_config(candidate_id: str, raw: dict[str, str]) -> dict[str, str]:
    _definition(candidate_id)
    base_url = _normalize_base_url(raw.get("base_url") or "")
    model = (raw.get("model") or "").strip()
    if not model or len(model) > 200:
        raise CandidateAdminError("Model must contain 1-200 characters.")
    api_key = (raw.get("api_key") or "").strip()
    if not api_key:
        stored = candidate_store.get_config(candidate_id)
        if stored is not None:
            api_key = stored["api_key"]
        else:
            api_key = candidates.environment_config(candidate_id)["api_key"]
    if not api_key:
        raise CandidateAdminError("API key is required for the first validation.")
    if len(api_key) > 8192:
        raise CandidateAdminError("API key is too long.")
    return {"base_url": base_url, "api_key": api_key, "model": model}


def _provider_error(response: httpx.Response, api_key: str) -> str:
    message = ""
    try:
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or "")
        elif isinstance(error, str):
            message = error
    except Exception:
        message = ""
    safe = message.replace(api_key, "[redacted]").strip()[:300]
    suffix = f": {safe}" if safe else ""
    return f"Provider rejected the configuration (HTTP {response.status_code}){suffix}"


async def _probe_candidate(candidate_id: str, config: dict[str, str]) -> None:
    """Exercise the exact model with one minimal non-streaming completion."""
    del candidate_id  # reserved for provider-specific probes if one diverges
    url = f"{config['base_url']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "stream": False,
        "max_tokens": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=VALIDATION_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise CandidateValidationError(
            f"Could not reach the provider: {exc.__class__.__name__}"
        ) from exc
    if response.status_code >= 400:
        raise CandidateValidationError(
            _provider_error(response, config["api_key"])
        )
    try:
        data = response.json()
    except Exception as exc:
        raise CandidateValidationError(
            "Provider returned a non-JSON response."
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("choices"), list):
        raise CandidateValidationError(
            "Provider response did not contain a chat completion."
        )


def _public_candidate(definition: dict[str, str]) -> dict:
    candidate_id = definition["id"]
    stored = candidate_store.get_config(candidate_id)
    environment = candidates.environment_config(candidate_id)
    if stored is not None:
        config = stored
        source = "stored"
    else:
        config = environment
        source = "environment" if all(environment.values()) else "none"
    return {
        "id": candidate_id,
        "name": definition["name"],
        "base_url": config["base_url"],
        "model": config["model"],
        "configured": bool(
            config["base_url"] and config["api_key"] and config["model"]
        ),
        "source": source,
        "has_saved_key": stored is not None and bool(stored["api_key"]),
        "has_api_key": bool(config["api_key"]),
        "verified_at": stored["verified_at"] if stored is not None else None,
        "editable": True,
    }


def workspace() -> dict:
    return {
        "candidates": [
            _public_candidate(definition)
            for definition in candidates.manageable_candidates()
        ],
        "routes": [
            candidates.route_for_scenario(scenario)
            for scenario in candidates.MODEL_SCENARIOS
        ],
    }


def reveal_api_key(candidate_id: str, actor_user_id: str | None) -> str:
    normalized_id = _definition(candidate_id)["id"]
    api_key = candidates.resolve(normalized_id)["api_key"]
    if not api_key:
        raise CandidateAdminError("This model integration has no API key configured.")
    candidate_store.record_key_reveal(normalized_id, actor_user_id)
    return api_key


def save_route(
    scenario: str,
    candidate_id: str,
    actor_user_id: str | None,
) -> dict[str, str]:
    normalized_scenario = (scenario or "").strip().lower()
    if normalized_scenario not in candidates.MODEL_SCENARIOS:
        raise UnknownScenarioError(f"Unknown model scenario {scenario!r}")
    normalized_id = _definition(candidate_id)["id"]
    config = candidates.resolve(normalized_id)
    if not all(config.values()):
        raise CandidateAdminError(
            "Configure and validate this model before selecting it for a scenario."
        )
    candidate_store.save_route(
        normalized_scenario, normalized_id, actor_user_id,
    )
    return candidates.route_for_scenario(normalized_scenario)


async def validate(
    candidate_id: str,
    raw: dict[str, str],
    actor_user_id: str | None,
) -> dict:
    normalized_id = _definition(candidate_id)["id"]
    config = _full_config(normalized_id, raw)
    await _probe_candidate(normalized_id, config)
    issued = candidate_store.issue_validation(
        normalized_id, config, actor_user_id,
    )
    return {
        "validation_token": issued["token"],
        "validated_at": issued["validated_at"],
    }


def save(
    candidate_id: str,
    raw: dict[str, str],
    validation_token: str,
    actor_user_id: str | None,
) -> dict:
    normalized_id = _definition(candidate_id)["id"]
    config = _full_config(normalized_id, raw)
    candidate_store.save_validated(
        normalized_id, config, validation_token, actor_user_id,
    )
    return _public_candidate(_definition(normalized_id))
