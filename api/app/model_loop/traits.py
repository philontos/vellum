"""Trait job: for each enabled dimension, extract over a turn span (one LLM call
= one observation), Bayesian-merge into trait_current, snapshot to trait_history.
Batched cadence (spec §8) — caller decides when via the runner.

`extract_one` is the pure extract+merge seam (no DB write): production `run()`
calls it then persists; the eval calls it with an empty prior (cold start) and
just scores the result — no persistence, no read-back."""
from string import Template

from app.config.dimensions_loader import DIMENSION_MAP
from app.llm.client import chat_json
from app.model_loop import bayes
from app.model_loop._span import span_text
from app.store import memory, model


def _profile_summary(content: dict) -> str:
    if not content:
        return "(no prior profile)"
    return ", ".join(f"{k}={v.get('score')}" for k, v in content.items()
                     if isinstance(v, dict) and "score" in v) or "(no prior profile)"


async def extract_one(span: str, key: str, dim: dict, old_content: dict) -> dict:
    """Extract ONE dimension over a span and Bayesian-merge into old_content.
    Pure compute — NO DB write. `old_content={}` = cold start (single observation
    regularized toward the dimension prior). Returns the merged content dict."""
    prompt = Template(dim["_extract"]).safe_substitute(
        raw_entry=span, profile_summary=_profile_summary(old_content),
        rubric=dim.get("_rubric", ""))
    extracted = await chat_json(system_prompt=prompt, user_prompt="", stage="trait")
    return bayes.merge_subdims(key, old_content, extracted)


async def run(start_turn: int, end_turn: int) -> None:
    # user-only: the AI's replies are context, not evidence of the user's traits
    span = span_text(start_turn, end_turn, roles=("user",))
    if not span.strip():
        return
    for key, dim in DIMENSION_MAP.items():
        cur = model.get_trait(key)
        old_content = cur["content_json"] if cur else {}
        try:
            merged = await extract_one(span, key, dim, old_content)
        except Exception:
            continue                         # one bad dimension must not block others
        sample_count = (cur["sample_count"] if cur else 0) + 1
        model.set_trait(key, merged, sample_count)
