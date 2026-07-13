"""Request-local selection of one user's private data directory.

The account database is global, but every conversation/model database lives
under ``data/users/<opaque user id>/``.  A ContextVar keeps the existing store
APIs small: once middleware enters a user scope, all current DAO calls resolve
to that user's files, including async tasks spawned by that request.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import re


class MissingUserScopeError(RuntimeError):
    """A user-owned store was accessed without an authenticated user."""


_USER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_current_user_id: ContextVar[str | None] = ContextVar(
    "vellum_current_user_id", default=None
)


def current_user_id() -> str | None:
    return _current_user_id.get()


@contextmanager
def user_scope(user_id: str):
    """Route all user-owned storage calls in this block to ``user_id``."""
    if not _USER_ID_RE.fullmatch(user_id):
        raise ValueError("invalid user id")
    token = _current_user_id.set(user_id)
    try:
        yield
    finally:
        _current_user_id.reset(token)
