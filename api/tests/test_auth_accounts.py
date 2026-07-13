from app.auth import accounts, sessions


def test_password_authentication_and_session_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    accounts.run_migrations()

    user = accounts.create_user(
        username="alice",
        display_name="Alice",
        password="correct horse battery staple",
        role="owner",
    )

    assert user["username"] == "alice"
    assert user["role"] == "owner"
    assert "password_hash" not in user
    assert accounts.authenticate("alice", "wrong password") is None
    assert accounts.authenticate("alice", "correct horse battery staple")["id"] == user["id"]

    token = sessions.create(user["id"])
    assert sessions.resolve(token)["id"] == user["id"]
    sessions.revoke(token)
    assert sessions.resolve(token) is None


def test_disabled_account_cannot_authenticate_or_keep_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    accounts.run_migrations()
    user = accounts.create_user("bob", "Bob", "a sufficiently long password")
    token = sessions.create(user["id"])

    accounts.disable(user["id"])

    assert accounts.authenticate("bob", "a sufficiently long password") is None
    assert sessions.resolve(token) is None


def test_password_change_revokes_existing_sessions(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    user = accounts.create_user("alice", "Alice", "the original long password")
    token = sessions.create(user["id"])

    accounts.set_password(user["id"], "the replacement long password")

    assert accounts.authenticate("alice", "the original long password") is None
    assert accounts.authenticate("alice", "the replacement long password") is not None
    assert sessions.resolve(token) is None
