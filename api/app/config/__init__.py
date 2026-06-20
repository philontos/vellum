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

# Soft target for the fact board: reconcile is told to keep it around this size by
# merging near-duplicates (never by dropping unique, uncontradicted facts). A tighter
# board also makes each per-fact reconcile decision more accurate.
def facts_target_count() -> int: return _int("VELLUM_FACTS_TARGET", 40)

# Every N turns, the facts job runs a whole-board compaction pass to merge residual
# redundancy that per-fact reconcile can't reach. 0 disables it.
def facts_compact_every() -> int: return _int("VELLUM_FACTS_COMPACT_EVERY", 20)


# === Web search (optional) ===
# Off unless a provider AND its key are configured. The chat loop then offers a
# `web_search` tool the model can call on its own (see chat/tools/websearch.py).
def web_search_provider() -> str:    return (os.getenv("WEB_SEARCH_PROVIDER") or "").strip().lower()
def web_search_max_results() -> int: return _int("WEB_SEARCH_MAX_RESULTS", 5)
def web_search_depth() -> str:       return (os.getenv("WEB_SEARCH_DEPTH") or "basic").strip().lower()
def web_search_max_hops() -> int:    return _int("WEB_SEARCH_MAX_HOPS", 4)


def web_search_enabled() -> bool:
    """True only when a supported provider AND its credential are present, so an
    unconfigured deployment behaves exactly as before (tool never advertised)."""
    provider = web_search_provider()
    if provider == "tavily":
        return bool((os.getenv("TAVILY_API_KEY") or "").strip())
    return False


# === Feishu / Lark adapter (optional) ===
# A WebSocket long-connection bot that bridges Feishu private chats to vellum's
# brain. Off unless BOTH app credentials are present, so a deployment without
# them boots exactly as before (the adapter task is never started).
def feishu_app_id() -> str:     return (os.getenv("FEISHU_APP_ID") or "").strip()
def feishu_app_secret() -> str: return (os.getenv("FEISHU_APP_SECRET") or "").strip()
def feishu_enabled() -> bool:   return bool(feishu_app_id() and feishu_app_secret())
