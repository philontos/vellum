"""Phase 2: embeddings persist inside vellum.db (so SQLCipher covers them) and
the in-memory HNSW index is rebuilt from those rows — no standalone index.bin."""
from app.config import vector_dir
from app.store import vectors
from app.store.db import get_conn
from app.store.vectors import VectorStore


def test_embedding_row_written_to_db(migrated_db):
    VectorStore().add(8, [1.0, 0.0, 0.0])
    with get_conn() as conn:
        row = conn.execute(
            "SELECT label, dim FROM embeddings WHERE label = 8"
        ).fetchone()
    assert row is not None
    assert row["label"] == 8
    assert row["dim"] == 3


def test_rebuilds_index_from_db_after_process_restart(migrated_db):
    VectorStore().add(5, [0.1, 0.2, 0.3])
    VectorStore().add(6, [0.9, 0.0, 0.0])
    # simulate a fresh process: discard the in-memory index, forcing a rebuild
    # purely from the persisted rows.
    vectors._db_index["path"] = None
    hits = VectorStore().search([0.1, 0.2, 0.3], k=1)
    assert hits == [5]


def test_no_index_bin_file_on_disk(migrated_db):
    VectorStore().add(1, [1.0, 0.0])
    assert not (vector_dir() / "index.bin").exists()
    assert not (vector_dir() / "dim.txt").exists()
