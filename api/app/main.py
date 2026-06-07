from fastapi import FastAPI

from app.routes import chat as chat_routes
from app.routes import history as history_routes

app = FastAPI(title="Vellum")
app.include_router(chat_routes.router)
app.include_router(history_routes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
