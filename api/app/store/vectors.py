"""HNSW vector index. Holds embeddings + integer labels ONLY (no text).
Labels map back to source rows via the `vector_refs` table (see store.memory)."""
from pathlib import Path

import hnswlib
import numpy as np

from app.config import vector_dir

MAX_ELEMENTS = 1_000_000


class VectorStore:
    def __init__(self):
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
        if self._index_path.exists():
            self.index.load_index(str(self._index_path), max_elements=MAX_ELEMENTS)
        else:
            self.index.init_index(max_elements=MAX_ELEMENTS, ef_construction=200, M=16)
        self.index.set_ef(64)

    def add(self, label: int, embedding: list[float], *, save: bool = True):
        if self.dim is None:
            self.dim = len(embedding)
            self._dim_file.write_text(str(self.dim))
            self._load_or_init()
        self.index.add_items(
            np.array([embedding], dtype=np.float32),
            np.array([label]),
        )
        if save:
            self.save()

    def save(self):
        if self.index is not None:
            self.index.save_index(str(self._index_path))

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
