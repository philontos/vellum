"""Per-dimension trait eval: feed a conversation engineered to express ONE
target (dimension, sub-dimension, direction), run the REAL extract+merge over it,
then check the target moved the right way and non-target sub-dimensions did not
swing past a crosstalk tolerance. Dimension-agnostic — driven by the case's `dimension`.

Cold start by construction: each case is a single observation against an empty
prior, scored via the production `extract_one` seam (extract + bayes merge, NO DB
write, NO read-back). See spec §5."""
import json
from pathlib import Path

from app.config.dimensions_loader import DIMENSION_MAP
from app.model_loop import traits as traits_job

_DATA = Path(__file__).parent / "data" / "traits"


def direction_ok(direction: str, score: float) -> bool:
    if direction == "high":
        return score >= 60
    if direction == "low":
        return score <= 40
    return 40 <= score <= 60            # mid


async def run_case(case: dict) -> dict:
    dim = case["dimension"]
    target_sub = case["target"]["sub"]
    direction = case["target"]["direction"]
    tol = case.get("crosstalk_tolerance", 25)

    prior = DIMENSION_MAP[dim].get("score_range", [0, 100])
    prior_mid = (prior[0] + prior[1]) / 2

    # user-only span built directly from the case — no DB, cold start (empty prior)
    span = "\n".join(f"user: {line}" for line in case["conversation"])
    merged = await traits_job.extract_one(span, dim, DIMENSION_MAP[dim], {})

    target_score = (merged.get(target_sub) or {}).get("score")

    crosstalk_ok = True
    for sub, val in merged.items():
        if sub == target_sub or not isinstance(val, dict) or "score" not in val:
            continue
        if abs(val["score"] - prior_mid) > tol:
            crosstalk_ok = False

    return {
        "dimension": dim, "target_sub": target_sub, "direction": direction,
        "target_score": target_score,
        "direction_ok": target_score is not None and direction_ok(direction, target_score),
        "crosstalk_ok": crosstalk_ok,
    }


def load_cases() -> list[dict]:
    if not _DATA.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(_DATA.glob("*.json"))]
