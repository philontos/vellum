from app.store import memory, user_states


def test_state_snapshots_are_account_local_grounded_and_idempotent(migrated_db):
    user = memory.append_message("user", "I am more disappointed than last week.")
    snapshot = {
        "states": [{
            "dimension": "emotion",
            "text": "The user feels disappointed.",
            "evidence": [{"turn": user["turn"], "quote": "disappointed"}],
        }],
        "deltas": [{
            "dimension": "emotion",
            "text": "Disappointment increased since last week.",
            "reference": "unspecified_past",
            "evidence": [{
                "turn": user["turn"],
                "quote": "more disappointed than last week",
            }],
        }],
    }

    first = user_states.record(
        user_turn=user["turn"], stream="neutral", snapshot=snapshot,
        inquiry_id=3, run_id="run-1",
    )
    replay = user_states.record(
        user_turn=user["turn"], stream="neutral", snapshot=snapshot,
        inquiry_id=3, run_id="run-1",
    )

    assert replay["id"] == first["id"]
    assert user_states.recent(before_turn=user["turn"] + 1)[0]["snapshot"] == snapshot


def test_empty_state_snapshot_is_not_persisted(migrated_db):
    user = memory.append_message("user", "What is two plus two?")

    assert user_states.record(
        user_turn=user["turn"], stream="neutral",
        snapshot={"states": [], "deltas": []}, inquiry_id=None, run_id="run-2",
    ) is None
    assert user_states.recent() == []
