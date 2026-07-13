"""Web login/logout endpoints. There is deliberately no public signup."""
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import config
from app.auth import accounts, sessions
from app.auth.dependencies import require_user


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


@router.post("/login")
def login(body: LoginIn):
    if not config.auth_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user = accounts.authenticate(body.username, body.password)
    if user is None:
        # One generic response avoids disclosing whether a family username exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )
    token = sessions.create(user["id"])
    max_age = config.auth_session_days() * 86400
    response = JSONResponse({"user": user})
    response.set_cookie(
        key=config.auth_cookie_name(),
        value=token,
        max_age=max_age,
        httponly=True,
        secure=config.auth_cookie_secure(),
        samesite="strict",
        path="/",
    )
    return response


@router.get("/me")
def me(request: Request):
    if not config.auth_enabled():
        return {"enabled": False, "user": None}
    user = require_user(request)
    return {"enabled": True, "user": user}


@router.post("/logout")
def logout(request: Request):
    token = getattr(request.state, "auth_token", None)
    sessions.revoke(token)
    response = JSONResponse({"ok": True})
    response.delete_cookie(
        key=config.auth_cookie_name(),
        path="/",
        secure=config.auth_cookie_secure(),
        httponly=True,
        samesite="strict",
    )
    return response
