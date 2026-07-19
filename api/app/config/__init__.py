"""Env-driven paths. Lazy (functions, not module constants) so tests repoint
VELLUM_DATA_DIR per-test without import-order pain."""
import os
from pathlib import Path

from app.data_scope import MissingUserScopeError, current_user_id


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def auth_enabled() -> bool:
    return _bool("VELLUM_AUTH_ENABLED")


def base_data_dir() -> Path:
    """Deployment-wide state: auth.db plus the users/ directory."""
    return Path(os.getenv("VELLUM_DATA_DIR", "./data"))


def data_dir() -> Path:
    """The active user's private directory (or the legacy single-user root)."""
    user_id = current_user_id()
    if user_id is not None:
        return base_data_dir() / "users" / user_id
    if auth_enabled():
        raise MissingUserScopeError(
            "user-owned data was accessed without an authenticated user scope"
        )
    return base_data_dir()


def auth_db_path() -> Path:
    """Global identities/sessions DB; never follows the current user scope."""
    return base_data_dir() / "auth.db"


def prompt_db_path() -> Path:
    """Deployment-wide prompts and model access shared by every account.

    Eval workers temporarily repoint ``VELLUM_DATA_DIR`` at one user's directory;
    an explicit absolute override keeps them on the same control-plane database.
    """
    override = (os.getenv("VELLUM_PROMPT_DB_PATH") or "").strip()
    return Path(override) if override else base_data_dir() / "prompts.db"


def db_path() -> Path:
    return data_dir() / "vellum.db"


def observability_db_path() -> Path:
    """Dedicated DB for diagnostic traces + eval runs/results. Separate file from
    vellum.db so observability data is decoupled from the personal-model data and
    can be retained/consumed independently."""
    return data_dir() / "observability.db"


def vector_dir() -> Path:
    return data_dir() / "vectors"


def auth_cookie_name() -> str:
    return os.getenv("VELLUM_AUTH_COOKIE", "vellum_session")


def auth_cookie_secure() -> bool:
    return _bool("VELLUM_AUTH_COOKIE_SECURE")


def auth_session_days() -> int:
    return _int("VELLUM_AUTH_SESSION_DAYS", 30)


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def tail_size() -> int:        return _int("VELLUM_TAIL_SIZE", 20)
def response_tail_size() -> int:
    return max(1, _int("VELLUM_RESPONSE_TAIL_SIZE", 8))


def response_context_tokens() -> int:
    return max(512, _int("VELLUM_RESPONSE_CONTEXT_TOKENS", 8000))


def response_recall_tokens() -> int:
    return max(0, _int("VELLUM_RESPONSE_RECALL_TOKENS", 1800))


def response_fact_tokens() -> int:
    return max(0, _int("VELLUM_RESPONSE_FACT_TOKENS", 1200))


def inquiry_tail_size() -> int: return max(0, _int("VELLUM_INQUIRY_TAIL_SIZE", 6))
def inquiry_evidence_limit() -> int:
    return max(0, _int("VELLUM_INQUIRY_EVIDENCE_LIMIT", 12))


def inquiry_context_tokens() -> int:
    return max(256, _int("VELLUM_INQUIRY_CONTEXT_TOKENS", 6000))


def inquiry_max_questions() -> int:
    return max(0, _int("VELLUM_INQUIRY_MAX_QUESTIONS", 5))


def inquiry_ledger_tokens() -> int:
    return max(100, _int("VELLUM_INQUIRY_LEDGER_TOKENS", 3500))


def recall_k() -> int:         return _int("VELLUM_RECALL_K", 6)
def recall_min_sim() -> float: return _float("VELLUM_RECALL_MIN_SIM", 0.35)
def neighborhood_w() -> int:   return _int("VELLUM_NEIGHBORHOOD_W", 3)
def recall_max_hops() -> int:  return _int("VELLUM_RECALL_MAX_HOPS", 3)
def persona_name() -> str:     return os.getenv("VELLUM_PERSONA", "neutral")
def timezone_name() -> str:    return os.getenv("VELLUM_TIMEZONE", "Asia/Shanghai")
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


def web_search_configured() -> bool:
    """True only when a supported provider AND its credential are present. The
    web_search tool is advertised regardless (capability is decoupled from
    credentials); this gates execution-readiness — whether to actively encourage
    search in the prompt and lift the tool-loop hop ceiling."""
    provider = web_search_provider()
    if provider == "tavily":
        return bool((os.getenv("TAVILY_API_KEY") or "").strip())
    return False


# === Feishu / Lark adapter (deprecated; compatibility only) ===
# A WebSocket long-connection bot that bridges Feishu private chats to vellum's
# brain. Off unless BOTH app credentials are present, so a deployment without
# them boots exactly as before (the adapter task is never started).
def feishu_app_id() -> str:     return (os.getenv("FEISHU_APP_ID") or "").strip()
def feishu_app_secret() -> str: return (os.getenv("FEISHU_APP_SECRET") or "").strip()
def feishu_enabled() -> bool:   return bool(feishu_app_id() and feishu_app_secret())
