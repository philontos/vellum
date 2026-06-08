"""HNSW vector index. Holds embeddings + integer labels ONLY (no text).
Labels map back to source rows via the `vector_refs` table (see store.memory).

`memory_index()` swaps the on-disk index for a throwaway in-process one — used to
isolate eval-case scratch (recall) alongside db.memory_scratch: zero disk, gone
when the block exits."""
from contextlib import contextmanager

import hnswlib
import numpy as np

from app.config import vector_dir

MAX_ELEMENTS = 1_000_000

# When not None, VectorStore operates purely in memory against this shared state:
# {"index": hnswlib.Index | None, "dim": int | None}. Set by memory_index().
_mem: dict | None = None


@contextmanager
def memory_index():
    """Hold the vector index purely in memory (no files) for the duration."""
    global _mem
    prev = _mem
    _mem = {"index": None, "dim": None}
    try:
        yield
    finally:
        _mem = prev


class VectorStore:
    def __init__(self):
        self._mem = _mem is not None
        if self._mem:
            self.dim = _mem["dim"]
            self.index = _mem["index"]
            return
        d = vector_dir()
        d.mkdir(parents=True, exist_ok=True)
        self._index_path = d / "index.bin"
        self._dim_file = d / "dim.txt"
        self.index: hnswlib.Index | None = None
        self.dim: int | None = None
        if self._dim_file.exists():
            self.dim = int(self._dim_file.read_text().strip())
            self._load_or_init()

    def _load_or_init(self):
        self.index = hnswlib.Index(space="cosine", dim=self.dim)
        if not self._mem and self._index_path.exists():
            self.index.load_index(str(self._index_path), max_elements=MAX_ELEMENTS)
        else:
            self.index.init_index(max_elements=MAX_ELEMENTS, ef_construction=200, M=16)
        self.index.set_ef(64)

    def add(self, label: int, embedding: list[float], *, save: bool = True):
        if self.dim is None:
            self.dim = len(embedding)
            if self._mem:
                _mem["dim"] = self.dim
            else:
                self._dim_file.write_text(str(self.dim))
            self._load_or_init()
        self.index.add_items(
            np.array([embedding], dtype=np.float32),
            np.array([label]),
        )
        if self._mem:
            _mem["index"] = self.index        # share across instances in the block
        elif save:
            self.save()

    def save(self):
        if not self._mem and self.index is not None:
            self.index.save_index(str(self._index_path))

    def search_scored(self, embedding: list[float], k: int = 5) -> list[tuple[int, float]]:
        """Like search() but returns (label, cosine_similarity) pairs, highest first.
        hnswlib cosine 'distance' = 1 - similarity, so similarity = 1 - distance."""
        if self.index is None or self.index.get_current_count() == 0:
            return []
        if self.dim is not None and len(embedding) != self.dim:
            raise ValueError(f"Query dim {len(embedding)} != index dim {self.dim}")
        labels, distances = self.index.knn_query(
            np.array([embedding], dtype=np.float32),
            k=min(k, self.index.get_current_count()),
        )
        return [(int(l), 1.0 - float(d)) for l, d in zip(labels[0], distances[0])]

    def search(self, embedding: list[float], k: int = 5) -> list[int]:
        if self.index is None or self.index.get_current_count() == 0:
            return []
        if self.dim is not None and len(embedding) != self.dim:
            raise ValueError(f"Query dim {len(embedding)} != index dim {self.dim}")
        labels, _ = self.index.knn_query(
            np.array([embedding], dtype=np.float32),
            k=min(k, self.index.get_current_count()),
        )
        return labels[0].tolist()
