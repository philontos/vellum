"""In-memory eval scratch: SQLite + vector index isolation. A case run inside the
scratch must NOT touch the real vellum.db / on-disk vector index."""
from app.store import db, memory
from app.store.vectors import VectorStore, memory_index


def test_memory_scratch_isolates_sqlite(migrated_db):
    memory.append_message("user", "REAL")
    assert memory.max_turn() == 0

    with db.memory_scratch("case1"):
        assert memory.max_turn() == -1                 # fresh empty in-memory DB
        memory.append_message("user", "SCRATCH")
        assert memory.max_turn() == 0
        assert memory.recent_tail(5)[-1]["content"] == "SCRATCH"

    # real DB untouched
    assert memory.max_turn() == 0
    assert memory.recent_tail(5)[-1]["content"] == "REAL"


def test_memory_scratch_distinct_cases_dont_bleed(migrated_db):
    with db.memory_scratch("a"):
        memory.append_message("user", "A")
    with db.memory_scratch("b"):
        assert memory.max_turn() == -1                 # case b sees none of a's data
        memory.append_message("user", "B")
        assert memory.recent_tail(5)[-1]["content"] == "B"


def test_memory_index_isolates_vectors(migrated_db):
    VectorStore().add(1, [1.0, 0.0])                   # real on-disk index
    with memory_index():
        assert VectorStore().search([1.0, 0.0], k=1) == []   # fresh empty in-memory
        VectorStore().add(99, [0.0, 1.0])
        assert VectorStore().search([0.0, 1.0], k=1) == [99]
    assert VectorStore().search([1.0, 0.0], k=1) == [1]       # real index untouched
