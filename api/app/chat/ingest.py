"""Persist turns into the eternal stream. User turns are embedded + indexed
(searchable key); assistant turns are stored verbatim only (recalled via turn
linkage, never embedded — spec §6/§7)."""
import asyncio

from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore


def _embed_sync(text: str) -> list[float]:
    return asyncio.run(embed(text))


def persist_user(content: str) -> dict:
    msg = memory.append_message("user", content)
    label = memory.add_vector_ref("message", msg["id"])
    VectorStore().add(label, _embed_sync(content))
    return msg


def persist_assistant(content: str) -> dict:
    return memory.append_message("assistant", content)  # no embed
