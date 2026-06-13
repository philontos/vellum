"""One-off migration: encrypt the on-disk databases in place with VELLUM_DB_KEY.

    VELLUM_DB_KEY=<64-hex> python -m app.encrypt_db

Steps, in order:
  1. Fold any legacy standalone vectors/index.bin into vellum.db's `embeddings`
     table (so SQLCipher will cover the vectors), then delete the file.
  2. Re-encrypt vellum.db and observability.db via SQLCipher's sqlcipher_export,
     replacing each file atomically.

Idempotent: a file that is already encrypted is skipped, so re-running is safe.
"""
import os
import sys
from pathlib import Path

import hnswlib
import numpy as np

from app.config import db_path, observability_db_path, vector_dir
from app.store import crypto
from app.store.vectors import MAX_ELEMENTS


def is_encrypted(path: Path) -> bool:
    """True if `path` exists and cannot be read as a plaintext SQLite db."""
    if not path.exists():
        return False
    sqlite = crypto.sqlite_module()
    conn = sqlite.connect(str(path))
    try:
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return False  # opened with no key -> plaintext
    except sqlite.DatabaseError:
        return True
    finally:
        conn.close()


def encrypt_file(path: Path, key: str) -> None:
    """Encrypt a plaintext SQLite file in place using sqlcipher_export."""
    tmp = path.with_name(path.name + ".enc-tmp")
    if tmp.exists():
        tmp.unlink()
    safe_tmp = str(tmp).replace("'", "''")
    conn = crypto.sqlite_module().connect(str(path))  # plaintext source, no key
    try:
        conn.execute(f"ATTACH DATABASE '{safe_tmp}' AS enc KEY \"x'{key}'\"")
        conn.execute("SELECT sqlcipher_export('enc')")
        conn.execute("DETACH DATABASE enc")
    finally:
        conn.close()
    os.replace(tmp, path)  # atomic within the same directory


def fold_index_bin() -> int:
    """Move embeddings from a legacy vectors/index.bin into vellum.db's
    `embeddings` table (plaintext, pre-encryption). Returns the count folded;
    no-op (0) when there is no legacy index. Deletes the files afterward."""
    vdir = vector_dir()
    idx_path = vdir / "index.bin"
    dim_file = vdir / "dim.txt"
    if not idx_path.exists() or not dim_file.exists():
        return 0
    dim = int(dim_file.read_text().strip())
    index = hnswlib.Index(space="cosine", dim=dim)
    index.load_index(str(idx_path), max_elements=MAX_ELEMENTS)
    labels = index.get_ids_list()
    conn = crypto.sqlite_module().connect(str(db_path()))  # plaintext, no key
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS embeddings "
            "(label INTEGER PRIMARY KEY, vec BLOB NOT NULL, dim INTEGER NOT NULL)"
        )
        if labels:
            vecs = index.get_items(labels)
            conn.executemany(
                "INSERT OR REPLACE INTO embeddings(label, vec, dim) VALUES (?, ?, ?)",
                [
                    (int(lbl), np.asarray(vec, dtype=np.float32).tobytes(), dim)
                    for lbl, vec in zip(labels, vecs)
                ],
            )
        conn.commit()
    finally:
        conn.close()
    idx_path.unlink()
    dim_file.unlink()
    return len(labels)


def main() -> None:
    try:
        key = crypto.db_key()
    except ValueError as e:
        raise SystemExit(f"VELLUM_DB_KEY is invalid: {e}")
    if key is None:
        raise SystemExit(
            "VELLUM_DB_KEY (or VELLUM_DB_KEY_FILE) must be set to encrypt. "
            "Generate one with: python -m app.keygen"
        )
    if crypto.sqlite_module().__name__ != "sqlcipher3":
        raise SystemExit(
            "sqlcipher3 is not installed — cannot encrypt. Install it first "
            "(brew install sqlcipher && pip install sqlcipher3)."
        )

    vellum = db_path()
    if not is_encrypted(vellum):
        folded = fold_index_bin()
        if folded:
            print(f"folded {folded} legacy embedding(s) into vellum.db")

    for path, label in [(vellum, "vellum.db"), (observability_db_path(), "observability.db")]:
        if not path.exists():
            print(f"skip {label}: not found")
        elif is_encrypted(path):
            print(f"skip {label}: already encrypted")
        else:
            encrypt_file(path, key)
            print(f"encrypted {label}")
    print("done.", file=sys.stderr)


if __name__ == "__main__":
    main()
