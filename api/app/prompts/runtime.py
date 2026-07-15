"""Release snapshots pinned to one chat turn or background modeling batch."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.prompts.catalog import definitions
from app.prompts import service


@dataclass(frozen=True)
class PromptSnapshot:
    release_id: int | None
    release_version: int | None
    contents: Mapping[str, str]


_current: ContextVar[PromptSnapshot | None] = ContextVar(
    "vellum_prompt_snapshot", default=None
)


def active_snapshot() -> PromptSnapshot:
    release, released = service.load_active_release()
    contents = {
        definition.key: (
            released.get(definition.key, definition.default_content)
            if definition.editable else definition.default_content
        )
        for definition in definitions()
    }
    return PromptSnapshot(
        release_id=release["id"] if release else None,
        release_version=release["version"] if release else None,
        contents=MappingProxyType(contents),
    )


def current_snapshot() -> PromptSnapshot | None:
    return _current.get()


@contextmanager
def use_snapshot(snapshot: PromptSnapshot | None = None):
    selected = snapshot or active_snapshot()
    token = _current.set(selected)
    try:
        yield selected
    finally:
        _current.reset(token)


@contextmanager
def ensure_snapshot():
    selected = current_snapshot()
    if selected is not None:
        yield selected
        return
    with use_snapshot() as selected:
        yield selected


def resolve(key: str, fallback: str) -> str:
    snapshot = current_snapshot() or active_snapshot()
    return snapshot.contents.get(key, fallback)
