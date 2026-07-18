"""Signed, within-person modeling for Schwartz Basic Values.

Schwartz values are relative priorities in a motivational circle, not ten
independent 0–100 traits.  Conversation produces sparse evidence records; this
module projects the durable ledger into a complete ten-value view where 0 is the
person's own assessed mean.  Missing evidence stays missing, and recent salience
(`activation`) is deliberately separate from long-term priority.
"""
from __future__ import annotations

import hashlib
import math
import unicodedata
from datetime import datetime, timezone
from typing import Iterable


VALUE_KEYS = (
    "self_direction", "stimulation", "hedonism", "achievement", "power",
    "security", "conformity", "tradition", "benevolence", "universalism",
)

HIGHER_ORDER_AXES = (
    {
        "key": "openness_conservation",
        "left": "openness_to_change",
        "right": "conservation",
        "left_values": ("self_direction", "stimulation", "hedonism"),
        "right_values": ("security", "conformity", "tradition"),
    },
    {
        "key": "transcendence_enhancement",
        "left": "self_transcendence",
        "right": "self_enhancement",
        "left_values": ("universalism", "benevolence"),
        "right_values": ("achievement", "power", "hedonism"),
    },
)

DIRECTIONS = {"support", "oppose", "sacrifice"}
_REQUIRED_OBSERVATION_FIELDS = {
    "direction", "strength", "confidence", "basis", "episode", "evidence",
    "counterpart",
}
BASIS_PRIORITY_WEIGHT = {
    "costly_choice": 1.0,
    "tradeoff": 0.95,
    "repeated_behavior": 0.85,
    "self_statement": 0.65,
    "aspiration": 0.35,
    # Emotion/concern says that a value is active now, not that it wins durable
    # trade-offs.  It therefore never updates long-term priority by itself.
    "emotion": 0.0,
    # A low-weight bridge for installations upgrading from the old positive-only
    # 0–100 posterior.  Centering removes its shared positive baseline.
    "legacy": 0.2,
}
BASIS_ACTIVATION_WEIGHT = {
    "costly_choice": 0.8,
    "tradeoff": 0.9,
    "repeated_behavior": 0.45,
    "self_statement": 0.55,
    "aspiration": 0.65,
    "emotion": 1.0,
    "legacy": 0.0,
}


def _bounded_number(value, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return min(1.0, max(0.0, number))


def validate_extraction(extracted: dict) -> None:
    """Fail closed when a production/rebuild call does not match V2 JSON.

    In particular, an immutable V1 Prompt Release can otherwise keep returning
    positive-only ``score`` objects after a code deployment. Treating that as an
    empty V2 observation would falsely advance sample_count and may overwrite a
    rebuilt projection, so callers validate before any ledger/current write.
    """
    if not isinstance(extracted, dict):
        raise ValueError("Schwartz extraction must be a JSON object")
    expected = set(VALUE_KEYS)
    actual = set(extracted)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "none"
        extra = ", ".join(sorted(actual - expected)) or "none"
        raise ValueError(
            "Schwartz extraction keys did not match V2 schema "
            f"(missing: {missing}; extra: {extra})"
        )
    for key in VALUE_KEYS:
        value = extracted[key]
        if value is None:
            continue
        if not isinstance(value, dict):
            raise ValueError(f"Schwartz extraction {key} must be an object or null")
        missing = _REQUIRED_OBSERVATION_FIELDS - set(value)
        if missing:
            raise ValueError(
                f"Schwartz extraction {key} is missing: {', '.join(sorted(missing))}"
            )
        if value["direction"] not in DIRECTIONS:
            raise ValueError(f"Schwartz extraction {key} has invalid direction")
        if value["basis"] not in BASIS_PRIORITY_WEIGHT or value["basis"] == "legacy":
            raise ValueError(f"Schwartz extraction {key} has invalid basis")
        for field in ("strength", "confidence"):
            number = value[field]
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                raise ValueError(f"Schwartz extraction {key}.{field} must be numeric")
            if not 0 <= float(number) <= 1:
                raise ValueError(f"Schwartz extraction {key}.{field} must be within 0..1")
        if float(value["confidence"]) < 0.2:
            raise ValueError(f"Schwartz extraction {key}.confidence must be at least 0.2")
        if not str(value["episode"] or "").strip():
            raise ValueError(f"Schwartz extraction {key}.episode must not be empty")
        if not str(value["evidence"] or "").strip():
            raise ValueError(f"Schwartz extraction {key}.evidence must not be empty")
        counterpart = value["counterpart"]
        if counterpart is not None and (
            counterpart not in VALUE_KEYS or counterpart == key
        ):
            raise ValueError(f"Schwartz extraction {key}.counterpart is invalid")


def normalize_observations(extracted: dict, start_turn: int, end_turn: int) -> list[dict]:
    """Validate one LLM result and turn it into canonical ledger records.

    A batch contributes at most one record per value.  Mere topical mention is
    ignored even if a provider returns it despite the prompt, preventing topic
    frequency from masquerading as value priority.
    """
    records = []
    for key in VALUE_KEYS:
        value = extracted.get(key) if isinstance(extracted, dict) else None
        if not isinstance(value, dict):
            continue
        direction = value.get("direction")
        basis = value.get("basis")
        if direction not in DIRECTIONS or basis == "topic":
            continue
        if basis not in BASIS_PRIORITY_WEIGHT:
            continue
        confidence = _bounded_number(value.get("confidence"), 0.0)
        strength = _bounded_number(value.get("strength"), 0.0)
        evidence = str(value.get("evidence") or "").strip()
        if confidence < 0.2 or strength <= 0 or not evidence:
            continue
        episode = str(value.get("episode") or "").strip()
        normalized_episode = _normalized_episode(episode)
        if normalized_episode:
            digest = hashlib.sha256(normalized_episode.encode("utf-8")).hexdigest()[:20]
            episode_key = f"episode:{digest}:{key}"
        else:
            episode = f"turns {start_turn}–{end_turn}"
            episode_key = f"turns:{start_turn}-{end_turn}:{key}"
        counterpart = value.get("counterpart")
        if counterpart not in VALUE_KEYS or counterpart == key:
            counterpart = None
        records.append({
            "dimension": "schwartz",
            "subdimension": key,
            "episode_key": episode_key,
            "direction": direction,
            "strength": strength,
            "confidence": confidence,
            "basis": basis,
            "episode": episode[:160],
            "evidence": evidence[:160],
            "counterpart": counterpart,
            "start_turn": start_turn,
            "end_turn": end_turn,
            "occurrences": 1,
            "model_version": "schwartz-v2",
        })
    return records


def _normalized_episode(episode: str) -> str:
    chars = []
    for char in episode.casefold():
        category = unicodedata.category(char)
        chars.append(" " if category.startswith(("P", "Z")) else char)
    return " ".join("".join(chars).split())


def _direction_sign(direction: str) -> float:
    return 1.0 if direction == "support" else -1.0


def _parse_time(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _activation(rows: list[dict], now: datetime) -> float:
    signals = []
    for row in rows:
        basis_weight = BASIS_ACTIVATION_WEIGHT.get(row.get("basis"), 0.0)
        if basis_weight <= 0:
            continue
        observed = _parse_time(row.get("observed_at")) or now
        age_days = max(0.0, (now - observed).total_seconds() / 86_400)
        recency = math.exp(-math.log(2) * age_days / 30.0)
        signals.append(
            basis_weight
            * _bounded_number(row.get("strength"))
            * _bounded_number(row.get("confidence"))
            * recency
        )
    return min(1.0, max(signals, default=0.0))


def _stance(rows: list[dict]) -> tuple[str, bool]:
    weighted = [
        row for row in rows
        if BASIS_PRIORITY_WEIGHT.get(row.get("basis"), 0.0) > 0
    ]
    support = any(row.get("direction") == "support" for row in weighted)
    oppose = any(row.get("direction") == "oppose" for row in weighted)
    sacrifice = any(row.get("direction") == "sacrifice" for row in weighted)
    if support and (oppose or sacrifice):
        return "mixed", oppose
    if oppose:
        return "oppose", True
    if sacrifice:
        return "yielding", False
    if support:
        return "support", False
    return "unobserved", False


def _tier(priority: float | None, low: float | None, stance: str,
          confidence: float) -> str:
    if priority is None:
        return "unobserved"
    if stance == "oppose":
        return "explicit_opposition"
    if stance == "mixed":
        return "context_dependent"
    if confidence < 0.15:
        return "context_dependent"
    if confidence >= 0.35 and priority >= 0.25 and (low or -1) > 0:
        return "core_priority"
    if priority >= 0.08:
        return "higher_priority"
    if priority <= -0.08:
        return "relative_yielding"
    return "context_dependent"


def project(rows: Iterable[dict], now: datetime | None = None) -> dict[str, dict]:
    """Project evidence into the canonical ten-value, centered current view."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    grouped = {key: [] for key in VALUE_KEYS}
    for row in rows:
        key = row.get("subdimension")
        if key in grouped:
            grouped[key].append(dict(row))

    estimates: dict[str, dict] = {}
    raw_means = []
    for key in VALUE_KEYS:
        value_rows = grouped[key]
        weighted_sum = 0.0
        precision = 0.0
        evidence_count = 0
        for row in value_rows:
            basis_weight = BASIS_PRIORITY_WEIGHT.get(row.get("basis"), 0.0)
            if basis_weight <= 0 or row.get("direction") not in DIRECTIONS:
                continue
            confidence = _bounded_number(row.get("confidence"))
            occurrences = max(1, int(row.get("occurrences") or 1))
            # V1 occurrences came from a positive-selection-biased estimator.
            # Preserve their count for provenance, but cap their influence so a
            # real V2 trade-off can correct the bridge promptly.
            precision_occurrences = min(occurrences, 3) if row.get("basis") == "legacy" else occurrences
            tau = basis_weight * confidence * confidence * precision_occurrences
            weighted_sum += tau * _direction_sign(row["direction"]) * _bounded_number(row.get("strength"))
            precision += tau
            evidence_count += occurrences
        raw = weighted_sum / precision if precision > 0 else None
        if raw is not None:
            raw_means.append(raw)
        stance, explicit_opposition = _stance(value_rows)
        latest = sorted(
            value_rows,
            key=lambda row: (str(row.get("observed_at") or ""), int(row.get("id") or 0)),
            reverse=True,
        )[:3]
        estimates[key] = {
            "raw": raw,
            "precision": precision,
            "confidence": precision / (precision + 2.0) if precision > 0 else 0.0,
            "stance": stance,
            "explicit_opposition": explicit_opposition,
            "evidence_count": evidence_count,
            "effective_evidence": precision,
            "activation": _activation(value_rows, now),
            "latest_evidence": [
                {
                    "quote": row.get("evidence") or "",
                    "episode": row.get("episode") or "",
                    "direction": row.get("direction"),
                    "basis": row.get("basis"),
                    "counterpart": row.get("counterpart"),
                    "start_turn": row.get("start_turn"),
                    "end_turn": row.get("end_turn"),
                }
                for row in latest
            ],
        }

    person_mean = sum(raw_means) / len(raw_means) if raw_means else 0.0
    projected: dict[str, dict] = {}
    for key in VALUE_KEYS:
        estimate = estimates[key]
        raw = estimate.pop("raw")
        precision = estimate.pop("precision")
        if raw is None:
            priority = low = high = None
        else:
            # Dividing the centered [-2,2] difference by two yields a stable,
            # bounded [-1,1] index without inventing a 0–100 psychometric scale.
            priority = (raw - person_mean) / 2.0
            half_width = min(0.5, 0.35 / math.sqrt(max(precision, 0.05)) / 2.0)
            low = max(-1.0, priority - half_width)
            high = min(1.0, priority + half_width)
        confidence = estimate["confidence"]
        projected[key] = {
            "priority": round(priority, 3) if priority is not None else None,
            "interval": (
                [round(low, 3), round(high, 3)] if low is not None and high is not None
                else None
            ),
            "confidence": round(confidence, 3),
            "stance": estimate["stance"],
            "explicit_opposition": estimate["explicit_opposition"],
            "evidence_count": estimate["evidence_count"],
            "effective_evidence": round(estimate["effective_evidence"], 3),
            "activation": round(estimate["activation"], 3),
            "status": _tier(priority, low, estimate["stance"], confidence),
            "evidence": (
                estimate["latest_evidence"][0]["quote"]
                if estimate["latest_evidence"] else None
            ),
            "latest_evidence": estimate["latest_evidence"],
        }
    return projected


def _legacy_occurrences(key: str, history: list[dict]) -> int:
    scores = []
    for snapshot in history:
        item = (snapshot.get("content_json") or {}).get(key)
        score = item.get("score") if isinstance(item, dict) else None
        if isinstance(score, (int, float)):
            scores.append(float(score))
    if not scores:
        return 1
    changes = 1
    for previous, current in zip(scores, scores[1:]):
        if abs(current - previous) > 0.01:
            changes += 1
    return changes


def legacy_evidence(content: dict, history: list[dict]) -> list[dict]:
    """Create explicitly low-weight bridge records from a V1 0–100 posterior."""
    rows = []
    latest_time = history[-1].get("taken_at") if history else None
    for key in VALUE_KEYS:
        item = content.get(key)
        score = item.get("score") if isinstance(item, dict) else None
        if not isinstance(score, (int, float)):
            continue
        delta = max(-1.0, min(1.0, (float(score) - 50.0) / 50.0))
        rows.append({
            "dimension": "schwartz",
            "subdimension": key,
            "episode_key": f"legacy-v1:{key}",
            # A low V1 score was not verified explicit opposition.  Represent it
            # as relative sacrifice so the V2 UI cannot overclaim rejection.
            "direction": "support" if delta >= 0 else "sacrifice",
            "strength": abs(delta),
            "confidence": _bounded_number(item.get("confidence"), 0.35),
            "basis": "legacy",
            "episode": "legacy aggregate",
            "evidence": str(item.get("evidence") or "legacy 0–100 estimate"),
            "counterpart": None,
            "start_turn": None,
            "end_turn": None,
            "occurrences": _legacy_occurrences(key, history),
            "model_version": "schwartz-v1-bridge",
            "observed_at": latest_time,
        })
    return rows


def project_legacy(content: dict, history: list[dict]) -> dict[str, dict]:
    return project(legacy_evidence(content, history))


def is_v2(content: dict) -> bool:
    return any(
        isinstance(item, dict) and "priority" in item
        for item in content.values()
    )


def _mean_priority(values: tuple[str, ...], projected: dict[str, dict]) -> float | None:
    observed = [
        projected[key]["priority"] for key in values
        if isinstance(projected.get(key, {}).get("priority"), (int, float))
    ]
    return sum(observed) / len(observed) if observed else None


def higher_order_axes(projected: dict[str, dict]) -> list[dict]:
    axes = []
    for spec in HIGHER_ORDER_AXES:
        left = _mean_priority(spec["left_values"], projected)
        right = _mean_priority(spec["right_values"], projected)
        score = None if left is None or right is None else max(-1.0, min(1.0, (right - left) / 2))
        confidences = [
            projected[key]["confidence"]
            for key in (*spec["left_values"], *spec["right_values"])
            if projected.get(key, {}).get("priority") is not None
        ]
        axes.append({
            "key": spec["key"],
            "left": spec["left"],
            "right": spec["right"],
            "score": round(score, 3) if score is not None else None,
            "confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
        })
    return axes


def profile_payload(content: dict, history: list[dict], rows: list[dict]) -> dict:
    """Frontend/API contract, including a truthful V1 transition fallback."""
    if rows:
        projected = project(rows)
        bases = {row.get("basis") for row in rows}
        if bases == {"legacy"}:
            calibration = "legacy_bridge"
        elif "legacy" in bases:
            calibration = "mixed_evidence"
        else:
            calibration = "conversation_evidence"
    elif is_v2(content):
        empty = project([])
        projected = {key: content.get(key) or empty[key] for key in VALUE_KEYS}
        calibration = "conversation_evidence"
    else:
        projected = project_legacy(content, history)
        calibration = "legacy_bridge"
    assessed = sum(item.get("priority") is not None for item in projected.values())
    return {
        "kind": "schwartz_circumplex",
        "model_version": "schwartz-v2",
        "calibration": calibration,
        "scale": {
            "minimum": -1,
            "center": 0,
            "maximum": 1,
            "meaning": "within_person_relative_priority",
        },
        "coverage": {
            "assessed": assessed,
            "total": len(VALUE_KEYS),
            "evidence_count": sum(item.get("evidence_count", 0) for item in projected.values()),
        },
        "values": projected,
        "axes": higher_order_axes(projected),
    }
