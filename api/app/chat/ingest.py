"""Persist turns into the eternal stream. User turns are embedded + indexed
(searchable key); assistant turns are stored verbatim only (recalled via turn
linkage, never embedded — spec §6/§7)."""
from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore


async def persist_user(content: str) -> dict:
    msg = memory.append_message("user", content)
    label = memory.add_vector_ref("message", msg["id"])
    VectorStore().add(label, await embed(content))
    return msg


def persist_assistant(content: str) -> dict:
    return memory.append_message("assistant", content)  # no embed
