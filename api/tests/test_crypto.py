"""Phase 1: at-rest encryption key handling (app.store.crypto)."""
import pytest

from app.store import crypto

KEY_A = "ab" * 32  # 64 hex chars = 256-bit raw key
KEY_B = "cd" * 32

HAS_SQLCIPHER = crypto.sqlite_module().__name__ == "sqlcipher3"
needs_sqlcipher = pytest.mark.skipif(
    not HAS_SQLCIPHER, reason="sqlcipher3 not installed (plaintext fallback)"
)


def test_db_key_none_when_unset(monkeypatch):
    monkeypatch.delenv("VELLUM_DB_KEY", raising=False)
    monkeypatch.delenv("VELLUM_DB_KEY_FILE", raising=False)
    assert crypto.db_key() is None


def test_db_key_reads_env(monkeypatch):
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    assert crypto.db_key() == KEY_A


def test_db_key_rejects_bad_length(monkeypatch):
    monkeypatch.setenv("VELLUM_DB_KEY", "abcd")
    with pytest.raises(ValueError):
        crypto.db_key()


def test_db_key_rejects_non_hex(monkeypatch):
    monkeypatch.setenv("VELLUM_DB_KEY", "zz" * 32)
    with pytest.raises(ValueError):
        crypto.db_key()


def test_db_key_reads_key_file_trimming_whitespace(tmp_path, monkeypatch):
    monkeypatch.delenv("VELLUM_DB_KEY", raising=False)
    f = tmp_path / "key.hex"
    f.write_text(KEY_A + "\n")
    monkeypatch.setenv("VELLUM_DB_KEY_FILE", str(f))
    assert crypto.db_key() == KEY_A


def test_env_var_takes_precedence_over_file(tmp_path, monkeypatch):
    f = tmp_path / "key.hex"
    f.write_text(KEY_B)
    monkeypatch.setenv("VELLUM_DB_KEY_FILE", str(f))
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    assert crypto.db_key() == KEY_A


def test_apply_key_noop_when_unset_leaves_plaintext(tmp_path, monkeypatch):
    monkeypatch.delenv("VELLUM_DB_KEY", raising=False)
    monkeypatch.delenv("VELLUM_DB_KEY_FILE", raising=False)
    p = tmp_path / "plain.db"
    conn = crypto.sqlite_module().connect(str(p))
    crypto.apply_key(conn)  # no key -> no-op
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    conn.close()
    assert p.read_bytes()[:6] == b"SQLite"  # ordinary plaintext sqlite header


@needs_sqlcipher
def test_apply_key_encrypts_at_rest(tmp_path, monkeypatch):
    p = tmp_path / "enc.db"
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    conn = crypto.sqlite_module().connect(str(p))
    crypto.apply_key(conn)
    conn.execute("CREATE TABLE t(x)")
    conn.execute("INSERT INTO t VALUES (7)")
    conn.commit()
    conn.close()
    assert p.read_bytes()[:6] != b"SQLite"  # encrypted: header is ciphertext


@needs_sqlcipher
def test_right_key_reads_back(tmp_path, monkeypatch):
    p = tmp_path / "enc.db"
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    conn = crypto.sqlite_module().connect(str(p))
    crypto.apply_key(conn)
    conn.execute("CREATE TABLE t(x)")
    conn.execute("INSERT INTO t VALUES (7)")
    conn.commit()
    conn.close()

    conn = crypto.sqlite_module().connect(str(p))
    crypto.apply_key(conn)
    assert conn.execute("SELECT x FROM t").fetchone()[0] == 7
    conn.close()


@needs_sqlcipher
def test_wrong_key_raises_locked(tmp_path, monkeypatch):
    p = tmp_path / "enc.db"
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    conn = crypto.sqlite_module().connect(str(p))
    crypto.apply_key(conn)
    conn.execute("CREATE TABLE t(x)")
    conn.commit()
    conn.close()

    monkeypatch.setenv("VELLUM_DB_KEY", KEY_B)
    conn = crypto.sqlite_module().connect(str(p))
    with pytest.raises(crypto.LockedDatabaseError):
        crypto.apply_key(conn)
    conn.close()


def test_apply_key_raises_when_key_set_but_no_sqlcipher(tmp_path, monkeypatch):
    """If a key is configured but the driver can't encrypt, fail loud — never
    silently write plaintext."""
    import sqlite3 as plain
    monkeypatch.setattr(crypto, "_sqlite", plain)
    monkeypatch.setenv("VELLUM_DB_KEY", KEY_A)
    conn = plain.connect(str(tmp_path / "x.db"))
    with pytest.raises(crypto.LockedDatabaseError):
        crypto.apply_key(conn)
    conn.close()
