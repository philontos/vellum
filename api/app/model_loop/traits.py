"""Trait job: for each enabled dimension, extract over a turn span (one LLM call
= one observation), Bayesian-merge into trait_current, snapshot to trait_history.
Batched cadence (spec §8) — caller decides when via the runner.

`extract_one` is the pure extract+merge seam (no DB write): production `run()`
calls it then persists; the eval calls it with an empty prior (cold start) and
just scores the result — no persistence, no read-back."""
from string import Template

from app.config.dimensions_loader import DIMENSION_MAP
from app.llm.client import chat_json
from app.model_loop import bayes, schwartz
from app.model_loop._span import span_text
from app.prompts import runtime
from app.store import memory, model


def _profile_summary(content: dict) -> str:
    if not content:
        return "(no prior profile)"
    scores = [
        f"{k}={v.get('score')}" for k, v in content.items()
        if isinstance(v, dict) and "score" in v
    ]
    priorities = [
        f"{k}={v.get('priority'):+.2f}"
        for k, v in content.items()
        if isinstance(v, dict) and isinstance(v.get("priority"), (int, float))
    ]
    episodes = []
    for key, value in content.items():
        if not isinstance(value, dict):
            continue
        for evidence in value.get("latest_evidence") or []:
            episode = evidence.get("episode") if isinstance(evidence, dict) else None
            if episode:
                episodes.append(f"{key}: {episode}")
    summary = ", ".join(priorities or scores)
    if episodes:
        summary += "; known episodes (copy the label when the same event returns): " + "; ".join(episodes[:12])
    return summary or "(no prior profile)"


async def _extract(span: str, key: str, dim: dict, old_content: dict) -> dict:
    with runtime.ensure_snapshot():
        template = runtime.resolve(f"traits.{key}.extract", dim["_extract"])
        rubric = runtime.resolve(f"traits.{key}.rubric", dim.get("_rubric", ""))
        prompt = Template(template).substitute(
            raw_entry=span,
            profile_summary=_profile_summary(old_content),
            rubric=rubric,
        )
        return await chat_json(
            system_prompt=prompt,
            user_prompt="",
            stage="trait",
            context={"dimension": key},
        )


async def extract_one(span: str, key: str, dim: dict, old_content: dict) -> dict:
    """Extract ONE dimension over a span and Bayesian-merge into old_content.
    Pure compute — NO DB write. `old_content={}` = cold start (single observation
    regularized toward the dimension prior). Returns the merged content dict."""
    extracted = await _extract(span, key, dim, old_content)
    if key == "schwartz":
        # Eval/cold-start seam.  Production uses the durable ledger in run().
        rows = schwartz.normalize_observations(extracted, start_turn=0, end_turn=0)
        return schwartz.project(rows)
    return bayes.merge_subdims(key, old_content, extracted)


async def run(start_turn: int, end_turn: int) -> None:
    # user-only: the AI's replies are context, not evidence of the user's traits
    with runtime.ensure_snapshot():
        span = span_text(start_turn, end_turn, roles=("user",))
        if not span.strip():
            return
        for key, dim in DIMENSION_MAP.items():
            cur = model.get_trait(key)
            old_content = cur["content_json"] if cur else {}
            try:
                extracted = await _extract(span, key, dim, old_content)
                if key == "schwartz":
                    schwartz.validate_extraction(extracted)
                    history = model.get_trait_history(key)
                    existing = model.get_trait_evidence(key)
                    if not existing and old_content and not schwartz.is_v2(old_content):
                        model.add_trait_evidence(
                            schwartz.legacy_evidence(old_content, history),
                        )
                    model.add_trait_evidence(
                        schwartz.normalize_observations(extracted, start_turn, end_turn),
                    )
                    merged = schwartz.project(model.get_trait_evidence(key))
                else:
                    merged = bayes.merge_subdims(key, old_content, extracted)
            except Exception:
                continue                     # one bad dimension must not block others
            sample_count = (cur["sample_count"] if cur else 0) + 1
            model.set_trait(key, merged, sample_count)
