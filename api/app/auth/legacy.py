"""One-time, rollback-friendly adoption of the old single-user databases."""
import os
import shutil
import uuid
from pathlib import Path

from app import config
from app.data_scope import user_scope
from app.store import crypto


class LegacyAdoptionError(RuntimeError):
    pass


_MAIN_TABLES = (
    "messages", "summaries", "vector_refs", "embeddings", "facts",
    "trait_current", "trait_history", "portrait_claims",
)
_OBS_TABLES = ("traces", "eval_runs", "eval_results")


def _has_rows(path: Path, tables: tuple[str, ...]) -> bool:
    if not path.exists():
        return False
    sqlite = crypto.sqlite_module()
    conn = sqlite.connect(path)
    crypto.apply_key(conn)
    try:
        existing = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if any(
            table in existing and conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
            for table in tables
        ):
            return True
        # Fresh schemas contain one empty dossier row and four -1 cursors. They
        # become meaningful user data once content/progress is written.
        if "messages" in tables:
            if "dossier" in existing and conn.execute(
                "SELECT 1 FROM dossier WHERE content <> '' LIMIT 1"
            ).fetchone():
                return True
            if "cursors" in existing and conn.execute(
                "SELECT 1 FROM cursors WHERE through_turn >= 0 LIMIT 1"
            ).fetchone():
                return True
        return False
    finally:
        conn.close()


def _checkpoint(path: Path) -> None:
    if not path.exists():
        return
    sqlite = crypto.sqlite_module()
    conn = sqlite.connect(path)
    crypto.apply_key(conn)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def adopt(user_id: str) -> list[str]:
    """Copy legacy DBs into ``user_id`` while retaining the originals as rollback.

    The application/service must be stopped while this runs so no writer can add
    a turn between the WAL checkpoint and the copy.
    """
    root = config.base_data_dir()
    source_main = root / "vellum.db"
    if not source_main.exists():
        raise LegacyAdoptionError(f"legacy database not found: {source_main}")

    target_dir = root / "users" / user_id
    target_main = target_dir / "vellum.db"
    target_obs = target_dir / "observability.db"
    if _has_rows(target_main, _MAIN_TABLES) or _has_rows(target_obs, _OBS_TABLES):
        raise LegacyAdoptionError("target user data is not empty; refusing to overwrite it")

    sources = [(source_main, target_main)]
    source_obs = root / "observability.db"
    if source_obs.exists():
        sources.append((source_obs, target_obs))
    for source, _target in sources:
        _checkpoint(source)

    target_dir.mkdir(parents=True, exist_ok=True)
    prepared: list[tuple[Path, Path]] = []
    try:
        for source, target in sources:
            tmp = target.with_name(f".{target.name}.adopt-{uuid.uuid4().hex}")
            shutil.copy2(source, tmp)
            prepared.append((tmp, target))
        for tmp, target in prepared:
            os.replace(tmp, target)
    finally:
        for tmp, _target in prepared:
            if tmp.exists():
                tmp.unlink()

    # Verify the copied DBs through the normal scoped DAOs, apply any migrations,
    # and discard a possible pre-adoption empty HNSW cache.
    from app.store import db, observability, vectors

    vectors.discard_path(target_main)
    observability.discard_path(target_obs)
    with user_scope(user_id):
        crypto.assert_db_accessible()
        db.run_migrations()
        if target_obs.exists():
            with observability.get_conn():
                pass
    return [target.name for _source, target in sources]
