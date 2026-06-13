from contextlib import contextmanager
from pathlib import Path

from app.config import db_path
from app.store import crypto

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


_scratch_uri: str | None = None


def _connect():
    """Open a connection. On-disk connections are unlocked with VELLUM_DB_KEY
    when set (see app.store.crypto); the ephemeral in-memory scratch never
    touches disk, so it is never keyed."""
    sqlite = crypto.sqlite_module()
    if _scratch_uri is not None:
        conn = sqlite.connect(_scratch_uri, uri=True)
    else:
        p = db_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite.connect(p)
        crypto.apply_key(conn)
    conn.row_factory = sqlite.Row
    return conn


@contextmanager
def memory_scratch(name: str):
    """Run a block against a throwaway in-memory SQLite DB (shared-cache) instead
    of the on-disk vellum.db — used to isolate eval-case scratch with ZERO disk,
    ZERO temp dir, ZERO mount. The DB is built fresh (migrations run) and vanishes
    when the block exits. NOT concurrency-safe (mutates a process-global connection
    target); the eval stream runs cases sequentially, in a subprocess."""
    global _scratch_uri
    uri = f"file:{name}?mode=memory&cache=shared"
    # keepalive holds the in-memory DB alive; must use the SAME driver as
    # _connect() so the shared-cache namespace matches.
    keep = crypto.sqlite_module().connect(uri, uri=True)
    prev, _scratch_uri = _scratch_uri, uri
    try:
        run_migrations()
        yield
    finally:
        _scratch_uri = prev
        keep.close()


@contextmanager
def get_conn():
    """Short-lived connection. Commits on clean exit, always closes."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def run_migrations() -> None:
    with get_conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            # executescript issues an implicit COMMIT, so applying the migration and
            # recording it below are NOT one atomic transaction. That is safe here:
            # every migration is idempotent (CREATE ... IF NOT EXISTS / INSERT OR
            # IGNORE), so a crash before the INSERT just re-applies harmlessly next
            # boot. We keep executescript (not a fragile ';' split) so multi-statement
            # SQL / triggers stay correct.
            conn.executescript(path.read_text())
            conn.execute("INSERT INTO schema_migrations(name) VALUES (?)", (path.name,))
