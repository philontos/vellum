"""External-evaluator model config. Generation + judging use EVAL_GEN_*, which
MUST differ from the system-under-test model (LLM_*) — otherwise a model would
grade its own work. Mirrors the LLM_* preset fallback shape loosely; for evals we
require explicit EVAL_GEN_BASE_URL / EVAL_GEN_API_KEY / EVAL_GEN_MODEL."""
import os

from app.llm.client import resolve_structured_llm_config


def eval_gen_config() -> dict:
    return {
        "base_url": (os.getenv("EVAL_GEN_BASE_URL") or "").strip().rstrip("/"),
        "api_key": (os.getenv("EVAL_GEN_API_KEY") or "").strip(),
        "model": (os.getenv("EVAL_GEN_MODEL") or "").strip(),
    }


def is_configured() -> bool:
    c = eval_gen_config()
    return bool(c["base_url"] and c["api_key"] and c["model"])


def enforce_distinct_model() -> None:
    """Refuse to run if the evaluator model equals the system model."""
    if not is_configured():
        raise RuntimeError(
            "Eval generator not configured. Set EVAL_GEN_BASE_URL / EVAL_GEN_API_KEY "
            "/ EVAL_GEN_MODEL (a model DIFFERENT from LLM_MODEL)."
        )
    system_model = resolve_structured_llm_config().get("model", "")
    if eval_gen_config()["model"] == system_model:
        raise RuntimeError(
            f"EVAL_GEN_MODEL and the system LLM_MODEL must differ (both are "
            f"{system_model!r}) — using the same model to generate and grade defeats the eval."
        )
