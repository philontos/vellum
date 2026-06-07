"""Trait job: for each enabled dimension, extract over a turn span (one LLM call
= one observation), Bayesian-merge into trait_current, snapshot to trait_history.
Batched cadence (spec §8) — caller decides when via the runner."""
from string import Template

from app.config.dimensions_loader import DIMENSION_MAP
from app.llm.client import chat_json
from app.model_loop import bayes
from app.store import memory, model


def _span_text(start_turn: int, end_turn: int) -> str:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


def _profile_summary(dimension: str) -> str:
    cur = model.get_trait(dimension)
    if not cur:
        return "(no prior profile)"
    return ", ".join(f"{k}={v.get('score')}" for k, v in cur["content_json"].items()
                     if isinstance(v, dict) and "score" in v) or "(no prior profile)"


async def run(start_turn: int, end_turn: int) -> None:
    span = _span_text(start_turn, end_turn)
    if not span.strip():
        return
    for key, dim in DIMENSION_MAP.items():
        prompt = Template(dim["_extract"]).safe_substitute(
            raw_entry=span, profile_summary=_profile_summary(key), rubric=dim.get("_rubric", ""))
        try:
            extracted = await chat_json(system_prompt=prompt, user_prompt="", stage="trait")
        except Exception:
            continue                         # one bad dimension must not block others
        cur = model.get_trait(key)
        old_content = cur["content_json"] if cur else {}
        sample_count = (cur["sample_count"] if cur else 0) + 1
        merged = bayes.merge_subdims(key, old_content, extracted)
        model.set_trait(key, merged, sample_count)
