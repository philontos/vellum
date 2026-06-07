"""External-evaluator model config. Generation + judging use EVAL_GEN_*. Using a
DIFFERENT model from the system under test (LLM_*) is recommended — a model
grading its own work is weaker, especially on the honesty/sycophancy axis — but
NOT required; same-model setups (one provider) are allowed with a warning."""
import os
import sys

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


def require_eval_gen() -> None:
    """Ensure the external evaluator (EVAL_GEN_*) is configured. Same model as
    LLM_* is allowed but warned — judging your own model is less trustworthy."""
    if not is_configured():
        raise RuntimeError(
            "Eval generator not configured. Set EVAL_GEN_BASE_URL / EVAL_GEN_API_KEY "
            "/ EVAL_GEN_MODEL."
        )
    system_model = resolve_structured_llm_config().get("model", "")
    if system_model and eval_gen_config()["model"] == system_model:
        print(
            f"[evals] note: EVAL_GEN_MODEL == LLM_MODEL ({system_model!r}); the model "
            "is grading itself — scores on the honesty/sycophancy axis are less "
            "trustworthy. Use a different EVAL_GEN_MODEL when you can.",
            file=sys.stderr,
        )
