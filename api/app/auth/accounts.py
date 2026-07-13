"""Account lifecycle. Accounts are provisioned by the VPS owner, not signup."""
import re
import uuid

from app.auth import db as auth_db
from app.auth import passwords
from app.data_scope import user_scope


_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
_ROLES = {"owner", "member"}


def _public(row) -> dict:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _normalize_username(username: str) -> str:
    value = username.strip().lower()
    if not _USERNAME_RE.fullmatch(value):
        raise ValueError(
            "username must be 2-64 lowercase letters, numbers, '.', '_' or '-'"
        )
    return value


def run_migrations() -> None:
    auth_db.run_migrations()


def create_user(
    username: str,
    display_name: str,
    password: str,
    role: str = "member",
) -> dict:
    run_migrations()
    username = _normalize_username(username)
    display_name = display_name.strip()
    if not display_name or len(display_name) > 80:
        raise ValueError("display name must contain 1-80 characters")
    if role not in _ROLES:
        raise ValueError("role must be 'owner' or 'member'")
    password_hash = passwords.hash_password(password)
    user_id = uuid.uuid4().hex
    with auth_db.get_conn() as conn:
        conn.execute(
            "INSERT INTO users(id, username, display_name, password_hash, role) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, display_name, password_hash, role),
        )
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    # A newly provisioned account is immediately usable and starts with a fully
    # migrated, empty personal store.
    from app.store import db as user_db

    with user_scope(user_id):
        user_db.run_migrations()
    return _public(row)


def authenticate(username: str, password: str) -> dict | None:
    run_migrations()
    try:
        username = _normalize_username(username)
    except ValueError:
        return None
    with auth_db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? AND status = 'active'",
            (username,),
        ).fetchone()
    password_hash = row["password_hash"] if row is not None else passwords.dummy_hash()
    valid = passwords.verify(password, password_hash)
    if row is None or not valid:
        return None
    return _public(row)


def get(user_id: str) -> dict | None:
    run_migrations()
    with auth_db.get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _public(row) if row else None


def get_by_username(username: str) -> dict | None:
    run_migrations()
    try:
        username = _normalize_username(username)
    except ValueError:
        return None
    with auth_db.get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return _public(row) if row else None


def list_users(*, include_disabled: bool = True) -> list[dict]:
    run_migrations()
    where = "" if include_disabled else " WHERE status = 'active'"
    with auth_db.get_conn() as conn:
        rows = conn.execute(f"SELECT * FROM users{where} ORDER BY created_at, id").fetchall()
    return [_public(row) for row in rows]


def active_owner() -> dict | None:
    run_migrations()
    with auth_db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE role = 'owner' AND status = 'active' "
            "ORDER BY created_at, id LIMIT 1"
        ).fetchone()
    return _public(row) if row else None


def disable(user_id: str) -> None:
    run_migrations()
    with auth_db.get_conn() as conn:
        conn.execute(
            "UPDATE users SET status = 'disabled', updated_at = datetime('now') "
            "WHERE id = ?",
            (user_id,),
        )
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def set_password(user_id: str, password: str) -> None:
    """Replace a password and revoke every existing session for that account."""
    run_migrations()
    password_hash = passwords.hash_password(password)
    with auth_db.get_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (password_hash, user_id),
        )
        if cur.rowcount == 0:
            raise ValueError("unknown user")
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
