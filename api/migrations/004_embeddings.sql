-- Vector embeddings live INSIDE vellum.db so they are covered by SQLCipher
-- (the standalone hnswlib index.bin was not). The HNSW graph is rebuilt in
-- memory from these rows on first use; only the raw vectors are persisted.
-- `label` matches vector_refs.label.
CREATE TABLE IF NOT EXISTS embeddings (
  label  INTEGER PRIMARY KEY,
  vec    BLOB    NOT NULL,
  dim    INTEGER NOT NULL
);
