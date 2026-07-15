import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app import bootstrap
from app.auth import accounts
from app.auth.dependencies import require_user
from app.auth.middleware import AuthContextMiddleware
from app.auth import routes as auth_routes
from app.routes import chat as chat_routes
from app.routes import diary as diary_routes
from app.routes import facts as fact_routes
from app.routes import history as history_routes
from app.routes import inspect as inspect_routes
from app.routes import prompts as prompt_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to start (with a clear message) if the db is encrypted but no key
    # is configured, then ensure the schema is present. The vector index is
    # rebuilt lazily from the db on first use.
    bootstrap.migrate_all()

    # Bridge Feishu private chats to vellum, in-process, only when configured.
    # Imported lazily so a deployment without lark-oapi/credentials boots
    # exactly as before and the test suite never starts the connection.
    feishu_task = None
    if config.feishu_enabled() and not config.auth_enabled():
        from app.feishu import adapter as feishu_adapter
        feishu_task = asyncio.create_task(feishu_adapter.run())
    elif config.feishu_enabled():
        # The first version keeps the existing Feishu identity owner-only.
        owner = accounts.active_owner()
        if owner is not None:
            from app.feishu import adapter as feishu_adapter
            feishu_task = asyncio.create_task(feishu_adapter.run(user_id=owner["id"]))

    try:
        yield
    finally:
        if feishu_task is not None:
            feishu_task.cancel()


def _web_dist_dir() -> Path:
    """Built web UI to serve. Override with VELLUM_WEB_DIST; default <repo>/web/dist."""
    override = os.environ.get("VELLUM_WEB_DIST")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Vellum", lifespan=lifespan)
    app.add_middleware(AuthContextMiddleware)
    protected = [Depends(require_user)]
    app.include_router(auth_routes.router)
    app.include_router(chat_routes.router, dependencies=protected)
    app.include_router(history_routes.router, dependencies=protected)
    app.include_router(diary_routes.router, dependencies=protected)
    app.include_router(fact_routes.router, dependencies=protected)
    app.include_router(inspect_routes.router, dependencies=protected)
    app.include_router(prompt_routes.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Serve the built single-page web UI from the same origin, if present. The
    # API routes above are registered first, so they take precedence over this
    # catch-all mount. In dev there is no dist/ — the mount is skipped and the
    # Vite dev server is used instead.
    dist = _web_dist_dir()
    if dist.is_dir():
        @app.get("/app/{path:path}", include_in_schema=False)
        def web_app_route(path: str):
            return FileResponse(dist / "index.html")

        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")

    return app


app = create_app()
