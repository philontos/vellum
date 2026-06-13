from contextlib import asynccontextmanager

from fastapi import FastAPI

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


app = FastAPI(title="Vellum", lifespan=lifespan)
app.include_router(chat_routes.router)
app.include_router(history_routes.router)
app.include_router(inspect_routes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
