import hashlib

from fastapi.testclient import TestClient

from app.auth import accounts
from app.llm import candidate_service, candidates
from app.llm.client import resolve_structured_llm_config
from app.main import create_app
from app.prompts.db import get_conn


def _client() -> TestClient:
    return TestClient(create_app())


def _payload(**overrides) -> dict:
    return {
        "base_url": "https://glm.example/v1",
        "api_key": "web-secret-key",
        "model": "glm-test",
        **overrides,
    }


def test_admin_workspace_lists_the_primary_model_without_eagerly_exposing_its_key(
    migrated_db, monkeypatch,
):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_API_KEY", "deepseek-server-secret")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")

    response = _client().get("/admin/model-candidates")

    assert response.status_code == 200
    assert "deepseek-server-secret" not in response.text
    items = response.json()["candidates"]
    assert [item["id"] for item in items] == ["primary", "glm", "kimi"]
    assert items[0] == {
        "id": "primary",
        "name": "Primary model",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "configured": True,
        "source": "environment",
        "has_saved_key": False,
        "has_api_key": True,
        "verified_at": None,
        "editable": True,
    }

    revealed = _client().get("/admin/model-candidates/primary/api-key")
    assert revealed.status_code == 200
    assert revealed.json() == {"api_key": "deepseek-server-secret"}
    assert revealed.headers["cache-control"] == "no-store"
    with get_conn() as conn:
        audit = conn.execute(
            "SELECT action, candidate_id FROM model_candidate_audit_events "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert dict(audit) == {
        "action": "key_revealed",
        "candidate_id": "primary",
    }


def test_candidate_admin_api_is_owner_only(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    accounts.create_user(
        "owner", "Owner", "a sufficiently long password", role="owner",
    )
    accounts.create_user(
        "member", "Member", "another sufficiently long password",
    )
    owner = _client()
    member = _client()
    assert owner.post(
        "/auth/login",
        json={"username": "owner", "password": "a sufficiently long password"},
    ).status_code == 200
    assert member.post(
        "/auth/login",
        json={"username": "member", "password": "another sufficiently long password"},
    ).status_code == 200

    assert owner.get("/admin/model-candidates").status_code == 200
    assert member.get("/admin/model-candidates").status_code == 403
    assert member.get(
        "/admin/model-candidates/primary/api-key"
    ).status_code == 403
    assert member.post(
        "/admin/model-candidates/glm/validate", json=_payload(),
    ).status_code == 403
    assert member.put(
        "/admin/model-candidates/glm",
        json={**_payload(), "validation_token": "not-a-ticket"},
    ).status_code == 403
    assert member.put(
        "/admin/model-routes/chat", json={"candidate_id": "glm"},
    ).status_code == 403


def test_primary_model_can_be_validated_and_saved_over_its_environment_fallback(
    migrated_db, monkeypatch,
):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_API_KEY", "old-deepseek-key")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    seen = []

    async def accept(candidate_id: str, config: dict[str, str]) -> None:
        seen.append((candidate_id, config))

    monkeypatch.setattr(candidate_service, "_probe_candidate", accept)
    payload = {
        "base_url": "https://deepseek-proxy.example/v1",
        "api_key": "new-deepseek-key",
        "model": "deepseek-reasoner",
    }
    client = _client()

    checked = client.post(
        "/admin/model-candidates/primary/validate", json=payload,
    )
    saved = client.put(
        "/admin/model-candidates/primary",
        json={**payload, "validation_token": checked.json()["validation_token"]},
    )

    assert checked.status_code == 200
    assert saved.status_code == 200
    assert seen == [("primary", payload)]
    assert saved.json()["source"] == "stored"
    assert candidates.resolve("primary") == {
        "base_url": "https://deepseek-proxy.example/v1",
        "api_key": "new-deepseek-key",
        "model": "deepseek-reasoner",
    }


def test_owner_can_route_chat_background_and_evaluation_independently(
    migrated_db, monkeypatch,
):
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_API_KEY", "deepseek-key")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    monkeypatch.setenv("GLM_API_KEY", "glm-key")
    monkeypatch.setenv("KIMI_API_KEY", "kimi-key")
    client = _client()

    initial = client.get("/admin/model-candidates").json()
    assert initial["routes"] == [
        {"scenario": "chat", "candidate_id": "primary", "source": "environment"},
        {
            "scenario": "background",
            "candidate_id": "primary",
            "source": "environment",
        },
        {
            "scenario": "evaluation",
            "candidate_id": "primary",
            "source": "environment",
        },
    ]

    assert client.put(
        "/admin/model-routes/chat", json={"candidate_id": "kimi"},
    ).status_code == 200
    assert client.put(
        "/admin/model-routes/background", json={"candidate_id": "glm"},
    ).status_code == 200
    assert client.put(
        "/admin/model-routes/evaluation", json={"candidate_id": "primary"},
    ).status_code == 200

    assert candidates.resolve_for_scenario("chat")["model"] == "kimi-k3"
    assert candidates.resolve_for_scenario("background")["model"] == "glm-5.2"
    assert candidates.resolve_for_scenario("evaluation")["model"] == "deepseek-chat"
    assert resolve_structured_llm_config(stage="chat")["model"] == "kimi-k3"
    assert resolve_structured_llm_config(stage="facts")["model"] == "glm-5.2"
    assert resolve_structured_llm_config(stage="eval")["model"] == "deepseek-chat"
    routed = client.get("/admin/model-candidates").json()["routes"]
    assert [route["source"] for route in routed] == ["stored", "stored", "stored"]

    missing = client.put(
        "/admin/model-routes/not-a-scenario", json={"candidate_id": "glm"},
    )
    assert missing.status_code == 404


def test_validation_must_succeed_before_exact_config_can_be_saved(
    migrated_db, monkeypatch,
):
    seen = []

    async def accept(candidate_id: str, config: dict[str, str]) -> None:
        seen.append((candidate_id, config))

    monkeypatch.setattr(candidate_service, "_probe_candidate", accept)
    client = _client()

    unvalidated = client.put(
        "/admin/model-candidates/glm",
        json={**_payload(), "validation_token": "not-a-ticket"},
    )
    assert unvalidated.status_code == 422
    assert "validate" in unvalidated.json()["detail"].lower()

    checked = client.post(
        "/admin/model-candidates/glm/validate", json=_payload(),
    )
    assert checked.status_code == 200
    ticket = checked.json()["validation_token"]
    assert ticket
    assert seen == [("glm", _payload())]

    changed = client.put(
        "/admin/model-candidates/glm",
        json={
            **_payload(model="glm-different"),
            "validation_token": ticket,
        },
    )
    assert changed.status_code == 422
    assert "changed" in changed.json()["detail"].lower()

    saved = client.put(
        "/admin/model-candidates/glm",
        json={**_payload(), "validation_token": ticket},
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["id"] == "glm"
    assert body["source"] == "stored"
    assert body["configured"] is True
    assert body["verified_at"]
    assert "api_key" not in body
    assert "web-secret-key" not in saved.text
    with get_conn() as conn:
        audit = "\n".join(
            row["details_json"]
            for row in conn.execute(
                "SELECT details_json FROM model_candidate_audit_events"
            ).fetchall()
        )
    assert "web-secret-key" not in audit

    assert candidates.resolve("glm") == {
        "base_url": "https://glm.example/v1",
        "api_key": "web-secret-key",
        "model": "glm-test",
    }
    monkeypatch.setenv("GLM_API_KEY", "environment-key")
    monkeypatch.setenv("GLM_MODEL", "environment-model")
    assert candidates.resolve("glm")["api_key"] == "web-secret-key"
    monkeypatch.setenv("LLM_CANDIDATE", "glm")
    assert resolve_structured_llm_config()["model"] == "glm-test"

    reused = client.put(
        "/admin/model-candidates/glm",
        json={**_payload(), "validation_token": ticket},
    )
    assert reused.status_code == 422


def test_saved_secret_can_be_reused_without_returning_it_to_the_browser(
    migrated_db, monkeypatch,
):
    async def accept(candidate_id: str, config: dict[str, str]) -> None:
        return None

    monkeypatch.setattr(candidate_service, "_probe_candidate", accept)
    client = _client()
    first = client.post(
        "/admin/model-candidates/kimi/validate",
        json=_payload(
            base_url="https://kimi.example/v1",
            api_key="kimi-stored-secret",
            model="kimi-k3",
        ),
    ).json()
    client.put(
        "/admin/model-candidates/kimi",
        json={
            **_payload(
                base_url="https://kimi.example/v1",
                api_key="kimi-stored-secret",
                model="kimi-k3",
            ),
            "validation_token": first["validation_token"],
        },
    ).raise_for_status()

    listed = client.get("/admin/model-candidates")
    assert listed.status_code == 200
    assert "kimi-stored-secret" not in listed.text
    kimi = next(
        item for item in listed.json()["candidates"] if item["id"] == "kimi"
    )
    assert kimi["has_saved_key"] is True

    checked = client.post(
        "/admin/model-candidates/kimi/validate",
        json=_payload(
            base_url="https://kimi.example/v1",
            api_key="",
            model="kimi-k3-updated",
        ),
    )
    assert checked.status_code == 200
    saved = client.put(
        "/admin/model-candidates/kimi",
        json={
            **_payload(
                base_url="https://kimi.example/v1",
                api_key="",
                model="kimi-k3-updated",
            ),
            "validation_token": checked.json()["validation_token"],
        },
    )
    assert saved.status_code == 200
    assert candidates.resolve("kimi")["api_key"] == "kimi-stored-secret"
    assert candidates.resolve("kimi")["model"] == "kimi-k3-updated"


def test_probe_uses_a_minimal_nonstreaming_completion_and_scrubs_key(
    migrated_db, monkeypatch,
):
    requests = []

    class Response:
        status_code = 401
        text = '{"error":{"message":"bad web-secret-key"}}'

        def json(self):
            return {"error": {"message": "bad web-secret-key"}}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            requests.append((url, headers, json))
            return Response()

    monkeypatch.setattr(candidate_service.httpx, "AsyncClient", lambda **kwargs: Client())

    response = _client().post(
        "/admin/model-candidates/glm/validate", json=_payload(),
    )

    assert response.status_code == 422
    assert "web-secret-key" not in response.text
    url, headers, body = requests[0]
    assert url == "https://glm.example/v1/chat/completions"
    assert headers["Authorization"] == "Bearer web-secret-key"
    assert body == {
        "model": "glm-test",
        "messages": [{"role": "user", "content": "Reply with OK only."}],
        "stream": False,
        "max_tokens": 1,
    }
    assert hashlib.sha256(b"web-secret-key").hexdigest() not in response.text
