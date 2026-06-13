"""Phase 4: git-backed sync of the encrypted db between devices.

Tests use a LOCAL bare repo as the 'remote' (file path) — no network. Two data
dirs stand in for two devices sharing one remote."""
import subprocess

import pytest

from app.store import crypto

KEY = "ab" * 32

HAS_SQLCIPHER = crypto.sqlite_module().__name__ == "sqlcipher3"
needs_sqlcipher = pytest.mark.skipif(
    not HAS_SQLCIPHER, reason="sqlcipher3 not installed"
)


@pytest.fixture
def remote(tmp_path):
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True,
                   capture_output=True)
    return str(bare)


def _seed_device(data_dir, monkeypatch, message):
    """Make `data_dir` an active device: encrypted vellum.db with one message."""
    monkeypatch.setenv("VELLUM_DATA_DIR", str(data_dir))
    monkeypatch.setenv("VELLUM_DB_KEY", KEY)
    from app.store import db, memory
    db.run_migrations()
    memory.append_message("user", message)


@needs_sqlcipher
def test_push_then_pull_moves_encrypted_db_between_devices(tmp_path, monkeypatch, remote):
    from app import sync
    monkeypatch.setenv("VELLUM_SYNC_REMOTE", remote)

    dev_a = tmp_path / "deviceA"
    _seed_device(dev_a, monkeypatch, "FROM_A")
    sync.push()

    # device B: fresh data dir, same remote + key
    dev_b = tmp_path / "deviceB"
    monkeypatch.setenv("VELLUM_DATA_DIR", str(dev_b))
    monkeypatch.setenv("VELLUM_DB_KEY", KEY)
    sync.pull()

    assert (dev_b / "vellum.db").read_bytes()[:6] != b"SQLite"  # arrived encrypted
    from app.store import memory
    assert any(m["content"] == "FROM_A" for m in memory.recent_tail(5))


@needs_sqlcipher
def test_pull_refuses_when_local_has_unpushed_changes(tmp_path, monkeypatch, remote):
    from app import sync
    from app.store import memory
    monkeypatch.setenv("VELLUM_SYNC_REMOTE", remote)

    # A pushes a baseline; B pulls it
    dev_a = tmp_path / "deviceA"
    _seed_device(dev_a, monkeypatch, "BASE")
    sync.push()

    dev_b = tmp_path / "deviceB"
    monkeypatch.setenv("VELLUM_DATA_DIR", str(dev_b))
    monkeypatch.setenv("VELLUM_DB_KEY", KEY)
    sync.pull()

    # A advances and pushes -> remote moves ahead of B
    monkeypatch.setenv("VELLUM_DATA_DIR", str(dev_a))
    memory.append_message("user", "A_SECOND")
    sync.push()

    # B makes a local-only commit without pulling -> B is now diverged
    monkeypatch.setenv("VELLUM_DATA_DIR", str(dev_b))
    memory.append_message("user", "B_DIVERGE")
    sync.commit_local()
    with pytest.raises(sync.SyncConflict):
        sync.pull()


@needs_sqlcipher
def test_status_reports_in_sync_after_push(tmp_path, monkeypatch, remote):
    from app import sync
    monkeypatch.setenv("VELLUM_SYNC_REMOTE", remote)
    dev = tmp_path / "dev"
    _seed_device(dev, monkeypatch, "X")
    sync.push()
    st = sync.status()
    assert st["ahead"] == 0
    assert st["behind"] == 0


def test_push_requires_remote(tmp_path, monkeypatch):
    from app import sync
    monkeypatch.delenv("VELLUM_SYNC_REMOTE", raising=False)
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path / "d"))
    with pytest.raises(SystemExit):
        sync.push()
