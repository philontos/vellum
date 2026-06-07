"""Bayesian conjugate recursive estimation for trait sub-dimensions. Ported from
engram profile_merge.py, adapted to operate on a content dict (the storage write
is done by the caller via model.set_trait). One observation per batch (spec §8)."""
from app.config.dimensions_loader import DIMENSION_MAP
from app.config.graph_rules import PROFILE_MERGE


def _score_prior(dimension: str) -> float:
    cfg = DIMENSION_MAP.get(dimension) or {}
    rng = cfg.get("score_range") or [0, 100]
    return (float(rng[0]) + float(rng[1])) / 2


def _confidence_display(tau: float) -> float:
    tau_ref = PROFILE_MERGE["tau_ref"]
    return tau / (tau + tau_ref) if tau + tau_ref > 0 else 0.0


def _bayes_update(old_score: float, old_tau: float, x: float, c: float) -> tuple[float, float]:
    gamma = PROFILE_MERGE["gamma"]
    tau_obs = c * c
    new_tau = gamma * old_tau + tau_obs
    alpha = tau_obs / new_tau if new_tau > 0 else 0.0
    new_score = old_score + alpha * (x - old_score)
    return new_score, new_tau


def merge_subdims(dimension: str, old_content: dict, new_content: dict) -> dict:
    """Merge one extraction (new_content: subkey -> {score,confidence,evidence}|null)
    into old_content (subkey -> {score,tau,confidence,evidence})."""
    tau_prior = PROFILE_MERGE["tau_prior"]
    min_conf = PROFILE_MERGE["min_conf"]
    prior = _score_prior(dimension)

    merged: dict = {}
    for key in set(old_content) | set(new_content):
        new_val = new_content.get(key)
        old_val = old_content.get(key)

        if new_val is None:                       # no signal → keep old
            if old_val is not None:
                merged[key] = old_val
            continue
        new_conf = float(new_val.get("confidence", 0.5))
        if new_conf < min_conf:                   # too unsure → keep old
            if old_val is not None:
                merged[key] = old_val
            continue

        if isinstance(old_val, dict) and "score" in old_val and "tau" in old_val:
            old_score, old_tau = float(old_val["score"]), float(old_val["tau"])
        else:
            old_score, old_tau = prior, tau_prior

        m_score, m_tau = _bayes_update(old_score, old_tau,
                                       float(new_val.get("score", prior)), new_conf)
        item = {"score": round(m_score, 2), "tau": round(m_tau, 4),
                "confidence": round(_confidence_display(m_tau), 3)}
        if "evidence" in new_val:
            item["evidence"] = new_val["evidence"]
        merged[key] = item
    return merged
