"""Owner-only deployment Prompt workspace and atomic release endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import require_owner
from app.prompts import service


router = APIRouter(prefix="/admin/prompts")


class DraftIn(BaseModel):
    content: str
    expected_revision: int


class PublishIn(BaseModel):
    expected_revision: int
    note: str = ""


class RestoreIn(BaseModel):
    expected_revision: int


def _actor(owner: dict | None) -> str | None:
    return owner["id"] if owner else None


def _translate(action):
    try:
        return action()
    except (service.UnknownPromptError, service.UnknownReleaseError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.ReadOnlyPromptError as exc:
        raise HTTPException(status_code=403, detail=f"read-only prompt: {exc}") from exc
    except service.RevisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except service.PublishValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("")
def get_workspace(owner: dict | None = Depends(require_owner)):
    return service.get_workspace()


@router.put("/{key}/draft")
def save_draft(key: str, body: DraftIn, owner: dict | None = Depends(require_owner)):
    return _translate(lambda: service.save_draft(
        key, body.content, body.expected_revision, _actor(owner)
    ))


@router.post("/publish")
def publish(body: PublishIn, owner: dict | None = Depends(require_owner)):
    return _translate(lambda: service.publish(
        body.expected_revision, body.note, _actor(owner)
    ))


@router.post("/releases/{release_id}/restore")
def restore(
    release_id: int, body: RestoreIn,
    owner: dict | None = Depends(require_owner),
):
    return _translate(lambda: service.restore_release(
        release_id, body.expected_revision, _actor(owner)
    ))
