"""Encrypted SQLite connection and forward-only migrations for auth state."""
from contextlib import contextmanager
from pathlib import Path

from app import config
from app.store import crypto


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "auth_migrations"


@contextmanager
def get_conn():
    path = config.auth_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    sqlite = crypto.sqlite_module()
    conn = sqlite.connect(path)
    crypto.apply_key(conn)
    conn.row_factory = sqlite.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def run_migrations() -> None:
    with get_conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name TEXT PRIMARY KEY, "
            "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {
            row["name"] for row in conn.execute("SELECT name FROM schema_migrations")
        }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            conn.executescript(path.read_text())
            conn.execute(
                "INSERT INTO schema_migrations(name) VALUES (?)", (path.name,)
            )
