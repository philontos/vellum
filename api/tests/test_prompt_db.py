from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier

from app import config
from app.prompts import db as prompt_db


def test_prompt_migrations_create_the_global_release_store(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))

    prompt_db.run_migrations()

    assert config.prompt_db_path() == tmp_path / "prompts.db"
    with prompt_db.get_conn() as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {
        "prompt_workspace",
        "prompt_drafts",
        "prompt_releases",
        "prompt_release_items",
        "prompt_audit_events",
        "schema_migrations",
    } <= names


def test_prompt_store_path_never_follows_a_user_scope(tmp_path, monkeypatch):
    from app.data_scope import user_scope

    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    with user_scope("alice"):
        assert config.prompt_db_path() == tmp_path / "prompts.db"
    with user_scope("bob"):
        assert config.prompt_db_path() == tmp_path / "prompts.db"


def test_prompt_migration_startup_is_safe_across_workers(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    barrier = Barrier(2)

    class CoordinatedConnection:
        def __init__(self, conn):
            self.conn = conn

        def execute(self, sql, params=()):
            cursor = self.conn.execute(sql, params)
            if sql == "SELECT name FROM schema_migrations":
                rows = cursor.fetchall()
                barrier.wait()
                return rows
            return cursor

        def executescript(self, script):
            return self.conn.executescript(script)

    @contextmanager
    def coordinated_conn():
        sqlite = prompt_db.crypto.sqlite_module()
        conn = sqlite.connect(config.prompt_db_path())
        conn.row_factory = sqlite.Row
        wrapped = CoordinatedConnection(conn)
        try:
            yield wrapped
            conn.commit()
        finally:
            conn.close()

    monkeypatch.setattr(prompt_db, "get_conn", coordinated_conn)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(prompt_db.run_migrations) for _ in range(2)]
        for future in futures:
            future.result()
