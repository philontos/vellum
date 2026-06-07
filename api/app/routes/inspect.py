"""Read-only inspection of the personal model + diagnostic traces (plus pin/note
on traces). For the web inspection panels — not part of the chat hot path."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.store import model, traces

router = APIRouter()


@router.get("/inspect/model")
def inspect_model():
    traits = model.all_traits()
    for t in traits:
        t["history"] = model.get_trait_history(t["dimension"])
    return {
        "dossier": model.get_dossier(),
        "dossier_meta": model.get_dossier_row(),
        "facts": model.all_facts(),
        "traits": traits,
    }


@router.get("/inspect/traces")
def inspect_traces(limit: int = 100, stage: str | None = None):
    return {"traces": traces.list_recent(limit=limit, stage=stage)}


class TracePatch(BaseModel):
    pinned: bool | None = None
    note: str | None = None


@router.post("/inspect/traces/{trace_id}")
def patch_trace(trace_id: int, body: TracePatch):
    if body.pinned is not None:
        traces.pin(trace_id, body.pinned)
    if body.note is not None:
        traces.set_note(trace_id, body.note)
    return {"ok": True}
