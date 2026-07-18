"""Grounded, independently-cursored personality extraction.

Each enabled dimension consumes only user turns. Generic score dimensions are
Bayesian-merged from exact quoted evidence without seeing their old aggregate;
Schwartz keeps its V2 relative-value ledger and may see old episode labels only
to deduplicate repeated discussion of the same event.
"""
from string import Template

from app.config.dimensions_loader import DIMENSION_MAP
from app.llm.client import chat_json
from app.model_loop import bayes, schwartz
from app.model_loop._span import span_text
from app.prompts import runtime
from app.store import memory, model


_WITHHELD_PRIOR = (
    "Historical aggregate deliberately withheld: score only the new evidence "
    "to avoid confirmation bias."
)


def _profile_summary(content: dict) -> str:
    """Expose only the Schwartz context needed to recognize prior episodes."""
    if not content:
        return "(no prior profile)"
    episodes = []
    for key, value in content.items():
        if not isinstance(value, dict):
            continue
        for evidence in value.get("latest_evidence") or []:
            episode = evidence.get("episode") if isinstance(evidence, dict) else None
            if episode:
                episodes.append(f"{key}: {episode}")
    if not episodes:
        return "(no known episodes; historical priorities withheld)"
    return (
        "Known episodes only (copy a label only when the same event returns): "
        + "; ".join(episodes[:12])
        + ". Historical aggregate priorities are deliberately withheld."
    )


async def _extract(
    span: str, key: str, dim: dict, old_content: dict | None = None,
) -> dict:
    with runtime.ensure_snapshot():
        template = runtime.resolve(f"traits.{key}.extract", dim["_extract"])
        rubric = runtime.resolve(f"traits.{key}.rubric", dim.get("_rubric", ""))
        prompt = Template(template).substitute(
            raw_entry=span,
            profile_summary=(
                _profile_summary(old_content or {})
                if key == "schwartz"
                else _WITHHELD_PRIOR
            ),
            rubric=rubric,
        )
        result = await chat_json(
            system_prompt=prompt,
            user_prompt="",
            stage="trait",
            scenario="background",
            context={"dimension": key},
        )
    return result if isinstance(result, dict) else {}


def _source_for_quote(quote: str, sources: list[dict]) -> dict | None:
    return next(
        (source for source in sources if quote and quote in source["content"]),
        None,
    )


def _validated_scores(
    extracted: dict, dim: dict, sources: list[dict],
) -> tuple[dict, list[dict]]:
    """Keep only bounded scores whose exact quote exists in a user turn."""
    cleaned: dict = {}
    observations: list[dict] = []
    for sub in dim.get("sub_dimensions") or []:
        subkey = sub["key"]
        value = extracted.get(subkey)
        if value is None:
            cleaned[subkey] = None
            continue
        try:
            score = float(value["score"])
            confidence = float(value["confidence"])
        except (KeyError, TypeError, ValueError):
            cleaned[subkey] = None
            continue
        quote = value.get("evidence")
        quote = quote.strip() if isinstance(quote, str) else ""
        source = _source_for_quote(quote, sources)
        if source is None or not 0 <= score <= 100 or not 0 <= confidence <= 1:
            cleaned[subkey] = None
            continue
        cleaned[subkey] = {
            "score": score,
            "confidence": confidence,
            "evidence": quote,
        }
        observations.append({
            "sub_dimension": subkey,
            "score": score,
            "confidence": confidence,
            "evidence_turn": source["turn"],
            "evidence_quote": quote,
        })
    return cleaned, observations


def grounded_schwartz_records(
    extracted: dict,
    sources: list[dict],
    start_turn: int,
    end_turn: int,
) -> list[dict]:
    """Validate V2 shape and retain only evidence quoted from a user turn."""
    schwartz.validate_extraction(extracted)
    grounded: dict = {}
    source_by_value: dict[str, dict] = {}
    for key in schwartz.VALUE_KEYS:
        value = extracted[key]
        if value is None:
            grounded[key] = None
            continue
        quote = str(value.get("evidence") or "").strip()
        source = _source_for_quote(quote, sources)
        if source is None:
            grounded[key] = None
            continue
        grounded[key] = {**value, "evidence": quote}
        source_by_value[key] = source

    records = schwartz.normalize_observations(grounded, start_turn, end_turn)
    for record in records:
        source = source_by_value[record["subdimension"]]
        source_turn = source.get("turn")
        if isinstance(source_turn, int) and source_turn >= 0:
            record["start_turn"] = source_turn
            record["end_turn"] = source_turn
        if source.get("created_at"):
            record["observed_at"] = source["created_at"]
    return records


async def extract_one(span: str, key: str, dim: dict, old_content: dict) -> dict:
    """Pure extract+merge seam used by evals; it performs no DB writes."""
    extracted = await _extract(span, key, dim, old_content)
    sources = [{"turn": -1, "content": span}]
    if key == "schwartz":
        records = grounded_schwartz_records(
            extracted, sources, start_turn=0, end_turn=0,
        )
        return schwartz.project(records)
    grounded, _ = _validated_scores(extracted, dim, sources)
    return bayes.merge_subdims(key, old_content, grounded)


async def run_dimension(
    start_turn: int, end_turn: int, dimension: str,
) -> None:
    dim = DIMENSION_MAP[dimension]
    rows = [
        row for row in memory.messages_in_turn_range(start_turn, end_turn)
        if row["role"] == "user"
    ]
    span = span_text(start_turn, end_turn, roles=("user",))
    if not span.strip() or not rows:
        model.apply_trait_batch(
            dimension=dimension,
            start_turn=start_turn,
            end_turn=end_turn,
            observations=[],
            content=None,
            sample_count=None,
        )
        return

    cur = model.get_trait(dimension)
    old_content = cur["content_json"] if cur else {}
    extracted = await _extract(span, dimension, dim, old_content)

    if dimension == "schwartz":
        records = grounded_schwartz_records(
            extracted, rows, start_turn=start_turn, end_turn=end_turn,
        )
        existing = model.get_trait_evidence(dimension)
        migrated_legacy = False
        if not existing and old_content and not schwartz.is_v2(old_content):
            legacy = schwartz.legacy_evidence(
                old_content, model.get_trait_history(dimension),
            )
            model.add_trait_evidence(legacy)
            migrated_legacy = bool(legacy)
        model.add_trait_evidence(records)
        has_signal = bool(records) or migrated_legacy
        merged = (
            schwartz.project(model.get_trait_evidence(dimension))
            if has_signal
            else None
        )
        model.apply_trait_batch(
            dimension=dimension,
            start_turn=start_turn,
            end_turn=end_turn,
            observations=[],
            content=merged,
            sample_count=(cur["sample_count"] if cur else 0) + 1
            if has_signal else None,
            accepted_count=len(records),
        )
        return

    grounded, observations = _validated_scores(extracted, dim, rows)
    merged = bayes.merge_subdims(dimension, old_content, grounded)
    has_signal = bool(observations)
    model.apply_trait_batch(
        dimension=dimension,
        start_turn=start_turn,
        end_turn=end_turn,
        observations=observations,
        content=merged if has_signal else None,
        sample_count=(cur["sample_count"] if cur else 0) + 1
        if has_signal else None,
    )


async def run(start_turn: int, end_turn: int) -> None:
    for key in DIMENSION_MAP:
        try:
            await run_dimension(start_turn, end_turn, key)
        except Exception:
            # One bad provider response or dimension must not skip the others.
            continue
