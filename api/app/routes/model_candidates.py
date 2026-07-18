"""Owner-only model credential validation and persistence endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import require_owner
from app.llm import candidate_service, candidate_store


router = APIRouter(prefix="/admin/model-candidates")


class CandidateConfigIn(BaseModel):
    base_url: str
    api_key: str = ""
    model: str


class CandidateSaveIn(CandidateConfigIn):
    validation_token: str


def _actor(owner: dict | None) -> str | None:
    return owner["id"] if owner is not None else None


def _translate(exc: Exception):
    if isinstance(exc, candidate_service.UnknownCandidateError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            candidate_service.CandidateAdminError,
            candidate_store.ValidationTicketError,
        ),
    ):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise exc


@router.get("")
def get_workspace(owner: dict | None = Depends(require_owner)):
    return candidate_service.workspace()


@router.post("/{candidate_id}/validate")
async def validate_candidate(
    candidate_id: str,
    body: CandidateConfigIn,
    owner: dict | None = Depends(require_owner),
):
    try:
        return await candidate_service.validate(
            candidate_id, body.model_dump(), _actor(owner),
        )
    except Exception as exc:
        return _translate(exc)


@router.put("/{candidate_id}")
def save_candidate(
    candidate_id: str,
    body: CandidateSaveIn,
    owner: dict | None = Depends(require_owner),
):
    try:
        values = body.model_dump()
        token = values.pop("validation_token")
        return candidate_service.save(
            candidate_id, values, token, _actor(owner),
        )
    except Exception as exc:
        return _translate(exc)
