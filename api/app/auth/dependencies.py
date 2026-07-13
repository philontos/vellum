"""FastAPI authorization dependencies."""
from fastapi import HTTPException, Request, status

from app import config


def require_user(request: Request) -> dict | None:
    """Return the authenticated user; preserve legacy mode when auth is off."""
    if not config.auth_enabled():
        return None
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user


def require_owner(request: Request) -> dict | None:
    user = require_user(request)
    if user is not None and user["role"] != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="owner access required",
        )
    return user
