"""Resolve an opaque session cookie and scope storage for the full request."""
from starlette.requests import HTTPConnection

from app import config
from app.auth import sessions
from app.data_scope import user_scope


class AuthContextMiddleware:
    """Pure ASGI middleware so user scope also covers streamed responses."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in {"http", "websocket"} or not config.auth_enabled():
            await self.app(scope, receive, send)
            return

        connection = HTTPConnection(scope)
        token = connection.cookies.get(config.auth_cookie_name())
        user = sessions.resolve(token)
        state = scope.setdefault("state", {})
        state["user"] = user
        state["auth_token"] = token

        if user is None:
            await self.app(scope, receive, send)
            return

        with user_scope(user["id"]):
            await self.app(scope, receive, send)
