from app import config
from app.data_scope import user_scope
from app.store import db, memory
from app.store import vectors
from app.store.vectors import VectorStore


def test_each_user_gets_an_independent_sqlite_store(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))

    with user_scope("user-a"):
        db.run_migrations()
        memory.append_message("user", "Alice secret")
        assert config.db_path() == tmp_path / "users" / "user-a" / "vellum.db"

    with user_scope("user-b"):
        db.run_migrations()
        memory.append_message("user", "Bob secret")
        assert [m["content"] for m in memory.recent_tail(10)] == ["Bob secret"]

    with user_scope("user-a"):
        assert [m["content"] for m in memory.recent_tail(10)] == ["Alice secret"]


def test_each_user_keeps_an_independent_in_memory_vector_index(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    vectors._db_indexes.clear()

    with user_scope("user-a"):
        db.run_migrations()
        VectorStore().add(1, [1.0, 0.0])
        alice_index = VectorStore().index

    with user_scope("user-b"):
        db.run_migrations()
        VectorStore().add(2, [0.0, 1.0])
        assert VectorStore().search([1.0, 0.0], k=1) == [2]

    with user_scope("user-a"):
        assert VectorStore().index is alice_index
        assert VectorStore().search([1.0, 0.0], k=1) == [1]
