from fastapi.testclient import TestClient

from app.auth import accounts
from app.main import create_app
from app.data_scope import user_scope
from app.store import memory


def test_auth_me_reports_legacy_mode_when_auth_is_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VELLUM_AUTH_ENABLED", raising=False)

    response = TestClient(create_app()).get("/auth/me")

    assert response.status_code == 200
    assert response.json() == {"enabled": False, "user": None}


def test_protected_api_requires_login_when_auth_is_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    accounts.run_migrations()
    accounts.create_user("alice", "Alice", "correct horse battery staple", role="owner")

    client = TestClient(create_app())

    assert client.get("/health").status_code == 200
    assert client.get("/history").status_code == 401


def test_login_cookie_scopes_history_to_the_authenticated_user(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    accounts.run_migrations()
    accounts.create_user("alice", "Alice", "correct horse battery staple", role="owner")

    client = TestClient(create_app())
    response = client.post(
        "/auth/login",
        json={"username": "alice", "password": "correct horse battery staple"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "alice"
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert client.get("/auth/me").json()["user"]["username"] == "alice"
    assert client.get("/history").status_code == 200

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/history").status_code == 401


def test_member_cannot_use_owner_only_eval_panel(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    accounts.create_user("member", "Member", "correct horse battery staple")

    client = TestClient(create_app())
    assert client.post(
        "/auth/login",
        json={"username": "member", "password": "correct horse battery staple"},
    ).status_code == 200

    assert client.get("/inspect/evals").status_code == 403
    assert client.get("/inspect/conversation-evals").status_code == 403
    assert client.get("/inspect/conversation-evals/records").status_code == 403
    assert client.post(
        "/inspect/conversation-evals/records",
        json={"assistant_turn": 1, "prompt_kind": "original"},
    ).status_code == 403


def test_two_login_cookies_read_only_their_own_history(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    alice = accounts.create_user("alice", "Alice", "correct horse battery staple")
    bob = accounts.create_user("bob", "Bob", "another correct horse battery staple")
    with user_scope(alice["id"]):
        memory.append_message("user", "alice only")
    with user_scope(bob["id"]):
        memory.append_message("user", "bob only")

    alice_client = TestClient(create_app())
    bob_client = TestClient(create_app())
    alice_client.post(
        "/auth/login",
        json={"username": "alice", "password": "correct horse battery staple"},
    )
    bob_client.post(
        "/auth/login",
        json={"username": "bob", "password": "another correct horse battery staple"},
    )

    assert [row["content"] for row in alice_client.get("/history").json()["messages"]] == ["alice only"]
    assert [row["content"] for row in bob_client.get("/history").json()["messages"]] == ["bob only"]
