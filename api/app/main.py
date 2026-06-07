from fastapi import FastAPI

app = FastAPI(title="Vellum")


@app.get("/health")
def health():
    return {"status": "ok"}
