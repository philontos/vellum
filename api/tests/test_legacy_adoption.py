from app.auth import accounts
from app.auth import legacy
from app.data_scope import user_scope
from app.store import db, memory, model, traces


def test_legacy_data_is_copied_into_owner_scope_and_source_is_retained(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VELLUM_AUTH_ENABLED", raising=False)
    db.run_migrations()
    memory.append_message("user", "existing private history")
    traces.record(
        turn=0, stage="chat", model="m", params={}, prompt="old trace", output="o",
        prompt_tokens=1, completion_tokens=1, duration_ms=1,
    )
    user = accounts.create_user("owner", "Owner", "a sufficiently long password", role="owner")

    copied = legacy.adopt(user["id"])

    assert copied == ["vellum.db", "observability.db"]
    assert (tmp_path / "vellum.db").exists()  # rollback copy remains untouched
    with user_scope(user["id"]):
        assert memory.recent_tail(10)[0]["content"] == "existing private history"
        assert traces.list_recent(10)[0]["prompt"] == "old trace"


def test_legacy_adoption_refuses_to_overwrite_nonempty_user_data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VELLUM_AUTH_ENABLED", raising=False)
    db.run_migrations()
    memory.append_message("user", "legacy")
    user = accounts.create_user("owner", "Owner", "a sufficiently long password", role="owner")
    with user_scope(user["id"]):
        memory.append_message("user", "already personal")

    try:
        legacy.adopt(user["id"])
    except legacy.LegacyAdoptionError as exc:
        assert "not empty" in str(exc)
    else:
        raise AssertionError("expected adoption to refuse a nonempty target")


def test_legacy_adoption_treats_a_written_dossier_as_user_data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VELLUM_AUTH_ENABLED", raising=False)
    db.run_migrations()
    user = accounts.create_user("owner", "Owner", "a sufficiently long password", role="owner")
    with user_scope(user["id"]):
        model.set_dossier("already modeled")

    try:
        legacy.adopt(user["id"])
    except legacy.LegacyAdoptionError:
        pass
    else:
        raise AssertionError("expected adoption to preserve a written dossier")
