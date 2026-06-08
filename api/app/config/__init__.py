"""Env-driven paths. Lazy (functions, not module constants) so tests repoint
VELLUM_DATA_DIR per-test without import-order pain."""
import os
from pathlib import Path


def data_dir() -> Path:
    return Path(os.getenv("VELLUM_DATA_DIR", "./data"))


def db_path() -> Path:
    return data_dir() / "vellum.db"


def observability_db_path() -> Path:
    """Dedicated DB for diagnostic traces + eval runs/results. Separate file from
    vellum.db so observability data is decoupled from the personal-model data and
    can be retained/consumed independently."""
    return data_dir() / "observability.db"


def vector_dir() -> Path:
    return data_dir() / "vectors"


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def tail_size() -> int:        return _int("VELLUM_TAIL_SIZE", 20)
def recall_k() -> int:         return _int("VELLUM_RECALL_K", 6)
def recall_min_sim() -> float: return _float("VELLUM_RECALL_MIN_SIM", 0.35)
def neighborhood_w() -> int:   return _int("VELLUM_NEIGHBORHOOD_W", 3)
def recall_max_hops() -> int:  return _int("VELLUM_RECALL_MAX_HOPS", 3)
def persona_name() -> str:     return os.getenv("VELLUM_PERSONA", "neutral")
def trait_batch_k() -> int:   return _int("VELLUM_TRAIT_K", 6)
def summary_span_s() -> int:  return _int("VELLUM_SUMMARY_S", 6)
def dossier_batch_m() -> int: return _int("VELLUM_DOSSIER_M", 12)
