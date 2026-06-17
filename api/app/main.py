import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import chat as chat_routes
from app.routes import history as history_routes
from app.routes import inspect as inspect_routes
from app.store import crypto, db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to start (with a clear message) if the db is encrypted but no key
    # is configured, then ensure the schema is present. The vector index is
    # rebuilt lazily from the db on first use.
    crypto.assert_db_accessible()
    db.run_migrations()
    yield


def _web_dist_dir() -> Path:
    """Built web UI to serve. Override with VELLUM_WEB_DIST; default <repo>/web/dist."""
    override = os.environ.get("VELLUM_WEB_DIST")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="Vellum", lifespan=lifespan)
    app.include_router(chat_routes.router)
    app.include_router(history_routes.router)
    app.include_router(inspect_routes.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Serve the built single-page web UI from the same origin, if present. The
    # API routes above are registered first, so they take precedence over this
    # catch-all mount. In dev there is no dist/ — the mount is skipped and the
    # Vite dev server is used instead.
    dist = _web_dist_dir()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="web")

    return app


app = create_app()
