"""Phase 1 wiring: the real DAO connections honour VELLUM_DB_KEY."""
import pytest

from app.store import crypto

KEY_A = "ab" * 32

HAS_SQLCIPHER = crypto.sqlite_module().__name__ == "sqlcipher3"
needs_sqlcipher = pytest.mark.skipif(
    not HAS_SQLCIPHER, reason="sqlcipher3 not installed (plaintext fallback)"
)


@needs_sqlcipher
def test_vellum_db_encrypted_on_disk_and_reads_back(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    from app.store import db, memory
    db.run_migrations()
    memory.append_message("user", "secret hello")

    p = tmp_path / "vellum.db"
    assert p.read_bytes()[:6] != b"SQLite"  # ciphertext, not a plaintext sqlite
    tail = memory.recent_tail(10)
    assert any(m["content"] == "secret hello" for m in tail)


@needs_sqlcipher
def test_observability_db_encrypted_on_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    # fresh import-state for the per-path schema cache
    import importlib
    from app.store import observability
    importlib.reload(observability)
    with observability.get_conn() as conn:
        conn.execute("INSERT INTO traces(stage, prompt) VALUES ('chat', 'secret')")

    p = tmp_path / "observability.db"
    assert p.read_bytes()[:6] != b"SQLite"


def test_keyless_stays_plaintext(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VELLUM_DB_KEY", raising=False)
    monkeypatch.delenv("VELLUM_DB_KEY_FILE", raising=False)
    from app.store import db, memory
    db.run_migrations()
    memory.append_message("user", "hi")

    p = tmp_path / "vellum.db"
    assert p.read_bytes()[:6] == b"SQLite"


@needs_sqlcipher
def test_assert_access_raises_clearly_on_encrypted_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    from app.store import db
    db.run_migrations()  # writes an encrypted vellum.db
    monkeypatch.delenv("VELLUM_DB_KEY")
    with pytest.raises(crypto.LockedDatabaseError):
        crypto.assert_db_accessible()


def test_assert_access_ok_for_plaintext_without_key(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VELLUM_DB_KEY", raising=False)
    monkeypatch.delenv("VELLUM_DB_KEY_FILE", raising=False)
    from app.store import db
    db.run_migrations()
    crypto.assert_db_accessible()  # must not raise


def test_assert_access_ok_when_no_db_yet(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path / "fresh"))
    monkeypatch.delenv("VELLUM_DB_KEY", raising=False)
    crypto.assert_db_accessible()  # fresh install, nothing to unlock


def test_in_memory_scratch_works_under_a_key(tmp_path, monkeypatch):
    """The ephemeral eval scratch never touches disk, so it must not be keyed —
    it should run fine even with VELLUM_DB_KEY set."""
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    from app.store import db, memory
    with db.memory_scratch("scratch-test"):
        memory.append_message("user", "ephemeral")
        assert memory.recent_tail(1)[0]["content"] == "ephemeral"
