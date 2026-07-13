"""Opaque server-side sessions; only a SHA-256 token digest is persisted."""
import hashlib
import secrets
import time

from app import config
from app.auth import db as auth_db


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create(user_id: str) -> str:
    auth_db.run_migrations()
    token = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + config.auth_session_days() * 86400
    with auth_db.get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
        conn.execute(
            "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_digest(token), user_id, expires_at),
        )
    return token


def resolve(token: str | None) -> dict | None:
    if not token:
        return None
    auth_db.run_migrations()
    now = int(time.time())
    with auth_db.get_conn() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.expires_at > ? AND u.status = 'active'",
            (_digest(token), now),
        ).fetchone()
        if row is None:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_digest(token),))
            return None
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def revoke(token: str | None) -> None:
    if not token:
        return
    auth_db.run_migrations()
    with auth_db.get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_digest(token),))
