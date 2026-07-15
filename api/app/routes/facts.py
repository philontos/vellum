"""Authenticated manual edits to the active durable-Facts board."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.store import model


router = APIRouter()

FACT_TEXT_MAX_CHARS = 4000


class FactPatch(BaseModel):
    text: str


def _validated_text(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fact text cannot be empty",
        )
    if len(text) > FACT_TEXT_MAX_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Fact text cannot exceed {FACT_TEXT_MAX_CHARS} characters",
        )
    return text


@router.patch("/facts/{fact_id}")
def patch_fact(fact_id: int, body: FactPatch):
    text = _validated_text(body.text)
    try:
        fact = model.replace_active_fact(fact_id, text)
    except model.FactConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    if fact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="active Fact not found",
        )
    return {"fact": fact}


@router.delete("/facts/{fact_id}")
def delete_fact(fact_id: int):
    return {"ok": True, "deleted": model.delete_active_fact(fact_id)}
