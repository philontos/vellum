from datetime import datetime, timezone

import pytest

from app.model_loop import schwartz
from app.store import model


def evidence(value, direction, strength=0.8, confidence=0.8, basis="tradeoff", **extra):
    return {
        "dimension": "schwartz",
        "subdimension": value,
        "episode_key": f"episode:{value}:{direction}",
        "direction": direction,
        "strength": strength,
        "confidence": confidence,
        "basis": basis,
        "evidence": extra.pop("quote", value),
        "counterpart": extra.pop("counterpart", None),
        "start_turn": extra.pop("start_turn", 1),
        "end_turn": extra.pop("end_turn", 3),
        "observed_at": extra.pop("observed_at", datetime.now(timezone.utc).isoformat()),
        "occurrences": extra.pop("occurrences", 1),
        **extra,
    }


def test_projection_is_complete_centered_and_signed():
    profile = schwartz.project([
        evidence("self_direction", "support", 0.95),
        evidence("security", "sacrifice", 0.8),
        evidence("achievement", "support", 0.55),
    ])

    assert list(profile) == list(schwartz.VALUE_KEYS)
    assessed = [v for v in profile.values() if v["priority"] is not None]
    assert sum(v["priority"] for v in assessed) == pytest.approx(0, abs=0.02)
    assert profile["self_direction"]["priority"] > profile["achievement"]["priority"] > 0
    assert profile["security"]["priority"] < 0
    assert profile["security"]["stance"] == "yielding"
    assert profile["tradition"]["status"] == "unobserved"


def test_relative_yielding_is_not_mislabeled_as_explicit_opposition():
    yielded = schwartz.project([evidence("security", "sacrifice")])["security"]
    opposed = schwartz.project([evidence("security", "oppose")])["security"]

    assert yielded["explicit_opposition"] is False
    assert yielded["stance"] == "yielding"
    assert opposed["explicit_opposition"] is True
    assert opposed["stance"] == "oppose"


def test_emotion_changes_activation_without_claiming_long_term_priority():
    item = schwartz.project([
        evidence("security", "support", basis="emotion", quote="I feel anxious"),
    ])["security"]

    assert item["priority"] is None
    assert item["activation"] > 0
    assert item["status"] == "unobserved"


def test_one_aspiration_stays_context_dependent_until_evidence_accumulates():
    profile = schwartz.project([
        evidence("achievement", "support", basis="aspiration", confidence=0.5),
        evidence("security", "sacrifice", basis="aspiration", confidence=0.5),
    ])

    assert profile["achievement"]["priority"] > 0
    assert profile["achievement"]["status"] == "context_dependent"


def test_normalize_abstains_on_topic_only_and_uses_one_episode_per_batch():
    rows = schwartz.normalize_observations({
        "power": {
            "direction": "support", "strength": 0.8, "confidence": 0.7,
            "basis": "topic", "evidence": "power structures", "counterpart": None,
        },
        "benevolence": {
            "direction": "support", "strength": 0.7, "confidence": 0.8,
            "basis": "self_statement", "evidence": "family comes first",
            "counterpart": None, "episode": "choosing family over relocation",
        },
    }, start_turn=10, end_turn=14)

    assert [r["subdimension"] for r in rows] == ["benevolence"]
    repeated = schwartz.normalize_observations({
        "benevolence": {
            "direction": "support", "strength": 0.8, "confidence": 0.9,
            "basis": "tradeoff", "evidence": "I still chose my family",
            "counterpart": None, "episode": " Choosing family over relocation ",
        },
    }, start_turn=20, end_turn=24)
    assert rows[0]["episode_key"] == repeated[0]["episode_key"]
    assert rows[0]["episode"] == "choosing family over relocation"


def test_evidence_store_is_idempotent_per_episode(migrated_db):
    row = evidence("benevolence", "support")
    assert model.add_trait_evidence([row]) == 1
    clarified = {**row, "confidence": 0.95, "strength": 0.9, "evidence": "clearer follow-up"}
    assert model.add_trait_evidence([clarified]) == 0
    stored = model.get_trait_evidence("schwartz")
    assert len(stored) == 1
    assert stored[0]["confidence"] == 0.95
    assert stored[0]["evidence"] == "clearer follow-up"
    assert stored[0]["occurrences"] == 1


def test_legacy_scores_are_presented_as_relative_not_absolute_strength():
    profile = schwartz.project_legacy({
        "achievement": {"score": 78, "tau": 8.0, "confidence": 0.7},
        "security": {"score": 76, "tau": 7.0, "confidence": 0.7},
        "conformity": {"score": 61, "tau": 3.0, "confidence": 0.4},
    }, history=[])

    assert profile["achievement"]["priority"] > 0
    assert profile["conformity"]["priority"] < 0
    assert profile["conformity"]["explicit_opposition"] is False
    assert profile["tradition"]["priority"] is None


def test_new_tradeoff_can_outweigh_many_positive_biased_legacy_updates():
    rows = [
        evidence(
            "security", "support", strength=0.6, confidence=0.8,
            basis="legacy", occurrences=30,
        ),
        evidence(
            "achievement", "support", strength=0.6, confidence=0.8,
            basis="legacy", occurrences=30,
        ),
        evidence(
            "security", "sacrifice", strength=0.95, confidence=0.9,
            basis="tradeoff", quote="accepted uncertainty",
        ),
    ]

    profile = schwartz.project(rows)

    assert profile["security"]["priority"] < 0
    assert profile["achievement"]["priority"] > 0
    assert profile["security"]["evidence_count"] == 31
