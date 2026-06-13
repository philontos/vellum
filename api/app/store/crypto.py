"""At-rest encryption for the on-disk SQLite databases.

Driver: SQLCipher via the `sqlcipher3` module when available, else stdlib
`sqlite3` (plaintext — for CI / dev machines without the native lib). Encryption
is opt-in: it activates only when VELLUM_DB_KEY (or VELLUM_DB_KEY_FILE) is set,
so existing keyless runs and the test suite behave exactly as before.

The key is a 256-bit raw key given as 64 hex chars, supplied by the *user* at
runtime and never written into the data dir. With a raw key SQLCipher skips
PBKDF2 — strength is the key's full 256-bit entropy, with no passphrase weak
link. Lose the key and the data is unrecoverable; there is no backdoor.
"""
import os

try:
    import sqlcipher3 as _sqlite
except ImportError:  # pragma: no cover - machines without the native lib
    import sqlite3 as _sqlite


class LockedDatabaseError(Exception):
    """Encrypted DB could not be opened with the configured key — wrong key,
    missing key, or a key is set but the driver cannot encrypt."""


def sqlite_module():
    """The DB-API module backing every connection (sqlcipher3 or sqlite3)."""
    return _sqlite


def db_key() -> str | None:
    """Configured 256-bit key as 64 lowercase hex chars, or None when encryption
    is off. VELLUM_DB_KEY wins over VELLUM_DB_KEY_FILE. Raises ValueError if a
    value is present but malformed."""
    raw = os.getenv("VELLUM_DB_KEY")
    if raw is None:
        path = os.getenv("VELLUM_DB_KEY_FILE")
        if path:
            with open(path) as f:  # user-held key file, kept outside the data dir
                raw = f.read()
    if raw is None:
        return None
    key = raw.strip()
    if len(key) != 64:
        raise ValueError(
            f"VELLUM_DB_KEY must be 64 hex chars (256-bit); got {len(key)}"
        )
    try:
        bytes.fromhex(key)
    except ValueError:
        raise ValueError("VELLUM_DB_KEY must be valid hexadecimal") from None
    return key.lower()


def apply_key(conn) -> None:
    """Unlock `conn` with the configured key. No-op when encryption is off.
    Probes the DB so a wrong/missing key fails fast here with a clear message
    instead of surfacing later as a cryptic 'file is not a database'."""
    key = db_key()
    if key is None:
        return
    if _sqlite.__name__ != "sqlcipher3":
        raise LockedDatabaseError(
            "VELLUM_DB_KEY is set but sqlcipher3 is not installed — refusing to "
            "open the database unencrypted. Install it with: "
            "brew install sqlcipher && pip install sqlcipher3"
        )
    conn.execute(f"PRAGMA key = \"x'{key}'\"")
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except _sqlite.DatabaseError as e:
        raise LockedDatabaseError(
            "could not open the database with VELLUM_DB_KEY — the key is wrong "
            "or missing"
        ) from e


def assert_db_accessible() -> None:
    """Fail fast (at startup) with a clear message if the on-disk vellum.db is
    encrypted but VELLUM_DB_KEY is missing or wrong — instead of a cryptic
    'file is not a database' surfacing later from inside a query. No-op when
    there is no db yet or it opens cleanly."""
    from app.config import db_path

    p = db_path()
    if not p.exists():
        return
    conn = _sqlite.connect(str(p))
    try:
        apply_key(conn)  # raises LockedDatabaseError when a key is set but wrong
        if db_key() is None:
            try:
                conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
            except _sqlite.DatabaseError as e:
                raise LockedDatabaseError(
                    "the database is encrypted but VELLUM_DB_KEY is not set — "
                    "set VELLUM_DB_KEY (or VELLUM_DB_KEY_FILE) to unlock it."
                ) from e
    finally:
        conn.close()
