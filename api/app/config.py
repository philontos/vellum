"""Env-driven paths. Lazy (functions, not module constants) so tests repoint
VELLUM_DATA_DIR per-test without import-order pain."""
import os
from pathlib import Path


def data_dir() -> Path:
    return Path(os.getenv("VELLUM_DATA_DIR", "./data"))


def db_path() -> Path:
    return data_dir() / "vellum.db"


def vector_dir() -> Path:
    return data_dir() / "vectors"
