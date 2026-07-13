"""HNSW vector index. The raw embeddings (float32) live in vellum.db's
`embeddings` table — so SQLCipher covers them — keyed by the same integer label
that `vector_refs` maps back to a source row (see store.memory). The hnswlib
graph itself is never written to disk: it is held in a process-global cache and
rebuilt from the persisted rows on first use (and whenever the active DB path
changes, e.g. across tests or VELLUM_DATA_DIR switches).

`memory_index()` swaps the db-backed index for a throwaway in-process one — used
to isolate eval-case scratch (recall) alongside db.memory_scratch: zero disk,
gone when the block exits."""
import os
from contextlib import contextmanager
from threading import RLock

import hnswlib
import numpy as np

from app.config import db_path
from app.store.db import get_conn

# HNSW capacity grows on demand (resize_index in VectorStore.add), so memory stays
# proportional to how many vectors actually exist. Pre-allocating millions of slots
# up front would OOM a small box (hnswlib zeroes the whole arena at init_index).
# Start modest; override with VELLUM_HNSW_INITIAL_ELEMENTS for more headroom.
INITIAL_ELEMENTS = max(1, int(os.getenv("VELLUM_HNSW_INITIAL_ELEMENTS", "4096")))

# When not None, VectorStore operates purely in memory against this shared state:
# {"index": hnswlib.Index | None, "dim": int | None}. Set by memory_index().
_mem: dict | None = None

# Process-global db-backed indexes, one per user DB path. Keeping a separate state
# prevents one request from swapping another request's HNSW graph mid-search.
_db_indexes: dict[str, dict] = {}
_db_indexes_lock = RLock()

# Backward-compatible view of the most recently used state (some low-level tests
# intentionally invalidate it to simulate a process restart).
_db_index: dict = {"path": None, "index": None, "dim": None, "lock": RLock()}


def discard_path(path) -> None:
    """Forget one cached graph after an out-of-band DB replacement/migration."""
    with _db_indexes_lock:
        _db_indexes.pop(str(path), None)


@contextmanager
def memory_index():
    """Hold the vector index purely in memory (no db, no files) for the duration."""
    global _mem
    prev = _mem
    _mem = {"index": None, "dim": None}
    try:
        yield
    finally:
        _mem = prev


def _new_index(dim: int, capacity: int | None = None) -> hnswlib.Index:
    cap = INITIAL_ELEMENTS if capacity is None else max(capacity, 1)
    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=cap, ef_construction=200, M=16)
    index.set_ef(64)
    return index


def _rebuild_from_db(path: str, state: dict) -> None:
    """Reload one path's in-memory index from its persisted embeddings."""
    state.update(path=path, index=None, dim=None)
    with get_conn() as conn:
        rows = conn.execute("SELECT label, vec, dim FROM embeddings").fetchall()
    if not rows:
        return
    dim = rows[0]["dim"]
    # size to the existing rows (+ headroom), not a fixed huge arena
    index = _new_index(dim, capacity=len(rows) + INITIAL_ELEMENTS)
    labels = np.array([r["label"] for r in rows])
    vecs = np.array(
        [np.frombuffer(r["vec"], dtype=np.float32) for r in rows], dtype=np.float32
    )
    index.add_items(vecs, labels)
    state.update(index=index, dim=dim)


def _state() -> dict:
    """The active index state — the scratch dict inside memory_index(), else the
    process-global db-backed one (rebuilt if the active DB path changed)."""
    if _mem is not None:
        return _mem
    cur = str(db_path())
    with _db_indexes_lock:
        state = _db_indexes.get(cur)
        if state is None:
            state = {"path": None, "index": None, "dim": None, "lock": RLock()}
            _db_indexes[cur] = state
    with state["lock"]:
        if state["path"] != cur:
            _rebuild_from_db(cur, state)
    global _db_index
    _db_index = state
    return state


class VectorStore:
    def __init__(self):
        self._mem = _mem is not None

    @property
    def index(self) -> hnswlib.Index | None:
        st = _state()
        with st.get("lock", _db_indexes_lock):
            return st["index"]

    @property
    def dim(self) -> int | None:
        st = _state()
        with st.get("lock", _db_indexes_lock):
            return st["dim"]

    def add(self, label: int, embedding: list[float], *, save: bool = True):
        st = _state()
        with st.get("lock", _db_indexes_lock):
            if st["dim"] is None:
                st["dim"] = len(embedding)
                st["index"] = _new_index(st["dim"])
            index = st["index"]
            # grow on demand so the arena stays proportional to actual usage
            if index.get_current_count() + 1 > index.get_max_elements():
                index.resize_index(index.get_max_elements() * 2)
            index.add_items(
                np.array([embedding], dtype=np.float32),
                np.array([label]),
            )
            if not self._mem and save:
                with get_conn() as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO embeddings(label, vec, dim) VALUES (?, ?, ?)",
                        (label, np.asarray(embedding, dtype=np.float32).tobytes(), st["dim"]),
                    )

    def search_scored(self, embedding: list[float], k: int = 5) -> list[tuple[int, float]]:
        """Like search() but returns (label, cosine_similarity) pairs, highest first.
        hnswlib cosine 'distance' = 1 - similarity, so similarity = 1 - distance."""
        st = _state()
        with st.get("lock", _db_indexes_lock):
            index = st["index"]
            if index is None or index.get_current_count() == 0:
                return []
            if st["dim"] is not None and len(embedding) != st["dim"]:
                raise ValueError(f"Query dim {len(embedding)} != index dim {st['dim']}")
            labels, distances = index.knn_query(
                np.array([embedding], dtype=np.float32),
                k=min(k, index.get_current_count()),
            )
            return [(int(l), 1.0 - float(d)) for l, d in zip(labels[0], distances[0])]

    def search(self, embedding: list[float], k: int = 5) -> list[int]:
        st = _state()
        with st.get("lock", _db_indexes_lock):
            index = st["index"]
            if index is None or index.get_current_count() == 0:
                return []
            if st["dim"] is not None and len(embedding) != st["dim"]:
                raise ValueError(f"Query dim {len(embedding)} != index dim {st['dim']}")
            labels, _ = index.knn_query(
                np.array([embedding], dtype=np.float32),
                k=min(k, index.get_current_count()),
            )
            return labels[0].tolist()
