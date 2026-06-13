"""Phase 3: plaintext -> encrypted migration, fold legacy index.bin, idempotency."""
import hnswlib
import numpy as np
import pytest

from app import encrypt_db
from app.config import vector_dir
from app.store import crypto

KEY = "ab" * 32

HAS_SQLCIPHER = crypto.sqlite_module().__name__ == "sqlcipher3"
needs_sqlcipher = pytest.mark.skipif(
    not HAS_SQLCIPHER, reason="sqlcipher3 not installed"
)


def _seed_plaintext(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VELLUM_DB_KEY", raising=False)
    monkeypatch.delenv("VELLUM_DB_KEY_FILE", raising=False)
    from app.store import db, memory, observability
    import importlib
    importlib.reload(observability)
    db.run_migrations()
    memory.append_message("user", "topsecret")
    with observability.get_conn() as c:
        c.execute("INSERT INTO traces(stage, prompt) VALUES ('chat', 'tracesecret')")


def test_main_requires_a_key(tmp_path, monkeypatch):
    _seed_plaintext(tmp_path, monkeypatch)
    # no VELLUM_DB_KEY set
    with pytest.raises(SystemExit):
        encrypt_db.main()


@needs_sqlcipher
def test_encrypts_both_dbs_and_data_survives(tmp_path, monkeypatch):
    _seed_plaintext(tmp_path, monkeypatch)
    assert (tmp_path / "vellum.db").read_bytes()[:6] == b"SQLite"  # plaintext first

    monkeypatch.setenv("VELLUM_DB_KEY", KEY)
    encrypt_db.main()

    assert (tmp_path / "vellum.db").read_bytes()[:6] != b"SQLite"
    assert (tmp_path / "observability.db").read_bytes()[:6] != b"SQLite"

    # data readable through the keyed connections
    from app.store import memory, observability
    import importlib
    importlib.reload(observability)
    assert any(m["content"] == "topsecret" for m in memory.recent_tail(5))
    with observability.get_conn() as c:
        prompts = [r["prompt"] for r in c.execute("SELECT prompt FROM traces")]
    assert "tracesecret" in prompts


@needs_sqlcipher
def test_folds_legacy_index_bin_into_encrypted_db(tmp_path, monkeypatch):
    _seed_plaintext(tmp_path, monkeypatch)
    vdir = vector_dir()
    vdir.mkdir(parents=True, exist_ok=True)
    idx = hnswlib.Index(space="cosine", dim=3)
    idx.init_index(max_elements=100, ef_construction=200, M=16)
    idx.add_items(np.array([[1.0, 0.0, 0.0]], dtype=np.float32), np.array([42]))
    idx.save_index(str(vdir / "index.bin"))
    (vdir / "dim.txt").write_text("3")

    monkeypatch.setenv("VELLUM_DB_KEY", KEY)
    encrypt_db.main()

    assert not (vdir / "index.bin").exists()
    assert not (vdir / "dim.txt").exists()
    from app.store import vectors
    from app.store.vectors import VectorStore
    vectors._db_index["path"] = None  # force rebuild from encrypted db
    assert VectorStore().search([1.0, 0.0, 0.0], k=1) == [42]


@needs_sqlcipher
def test_idempotent_second_run_is_noop(tmp_path, monkeypatch):
    _seed_plaintext(tmp_path, monkeypatch)
    monkeypatch.setenv("VELLUM_DB_KEY", KEY)
    encrypt_db.main()
    blob1 = (tmp_path / "vellum.db").read_bytes()
    encrypt_db.main()  # already encrypted -> skip, must not corrupt
    from app.store import memory
    assert any(m["content"] == "topsecret" for m in memory.recent_tail(5))
