import json

from app.inquiry import budget, context, store
from app.store import memory, model, user_states


def _ledger(cited_turn: int, quote: str):
    return {
        "goal": {
            "text": "Understand the recurring work conflict",
            "evidence": [{"turn": cited_turn, "quote": quote}],
        },
        "observations": [],
        "interpretations": [],
        "hypotheses": [],
        "blocking_unknowns": [{
            "id": "u1", "question": "What happened next?",
            "why_material": "It changes the interpretation", "status": "open",
            "resolved_after_turn": None,
        }],
        "asked_questions": [],
        "provisional_conclusion": None,
    }


def test_token_estimate_is_conservative_for_cjk_text():
    assert budget.estimate_tokens({"text": "辞" * 100}) >= 100


def test_controller_context_keeps_ledger_current_turn_and_cited_raw_evidence(
    migrated_db,
):
    old = memory.append_message("user", "My first conflict was during planning.")
    for number in range(8):
        memory.append_message(
            "user" if number % 2 == 0 else "assistant",
            f"recent-{number}",
        )
    current = memory.append_message("user", "It happened again today.")
    opened = store.open_inquiry(
        stream="neutral", opened_turn=old["turn"],
        ledger=_ledger(old["turn"], "first conflict"), decision={}, run_id="open",
    )

    built = context.build(stream="neutral", user_turn=current["turn"])

    assert built["current_user_turn"]["content"] == "It happened again today."
    assert built["inquiry"]["id"] == opened["id"]
    assert len(built["recent_messages"]) <= 6
    supplied_user_evidence = [
        *built["recent_messages"], *built["cited_evidence"],
    ]
    assert any(
        item["turn"] == old["turn"] and "first conflict" in item["content"]
        for item in supplied_user_evidence
    )
    assert built["budget"]["estimated_tokens"] <= built["budget"]["max_input_tokens"]
    assert budget.estimate_tokens(built) <= built["budget"]["max_input_tokens"]
    assert built["policy"] == {
        "max_questions": 5,
        "questions_asked": 0,
        "remaining_questions": 5,
    }


def test_controller_context_never_injects_personality_or_dossier(migrated_db):
    model.set_dossier("A potentially biasing portrait")
    model.add_fact("A durable fact")
    model.set_trait("ocean", {"O": {"score": 90}}, 1)
    current = memory.append_message("user", "Help me reason about this.")

    serialized = json.dumps(
        context.build(stream="neutral", user_turn=current["turn"]),
        ensure_ascii=False,
    )

    assert "potentially biasing portrait" not in serialized
    assert "durable fact" not in serialized
    assert '"score": 90' not in serialized


def test_controller_context_truncates_pathological_current_turn_to_hard_budget(
    migrated_db, monkeypatch,
):
    monkeypatch.setenv("VELLUM_INQUIRY_CONTEXT_TOKENS", "800")
    current = memory.append_message(
        "user", "START " + ("very long evidence " * 500) + " END",
    )

    built = context.build(stream="neutral", user_turn=current["turn"])

    assert built["budget"]["estimated_tokens"] <= 800
    assert budget.estimate_tokens(built) <= 800
    assert built["budget"]["current_user_turn_truncated"] is True
    assert built["current_user_turn"]["content"].startswith("START")
    assert built["current_user_turn"]["content"].endswith(" END")
    assert current["turn"] not in {
        item["turn"] for item in built["recent_messages"]
    }


def test_controller_context_exposes_older_paused_topics_as_bounded_summaries(
    migrated_db,
):
    first_user = memory.append_message("user", "Let us discuss the first topic.")
    first = store.open_inquiry(
        stream="neutral", opened_turn=first_user["turn"],
        ledger=_ledger(first_user["turn"], "first topic"),
        decision={}, run_id="first-open",
    )
    store.apply_revision(
        inquiry_id=first["id"], expected_revision=1, status="paused",
        ledger=_ledger(first_user["turn"], "first topic"),
        action="pause", user_turn=first_user["turn"], decision={},
        run_id="first-pause",
    )
    second_user = memory.append_message("user", "Now discuss the second topic.")
    second = store.open_inquiry(
        stream="neutral", opened_turn=second_user["turn"],
        ledger=_ledger(second_user["turn"], "second topic"),
        decision={}, run_id="second-open",
    )
    store.apply_revision(
        inquiry_id=second["id"], expected_revision=1, status="paused",
        ledger=_ledger(second_user["turn"], "second topic"),
        action="pause", user_turn=second_user["turn"], decision={},
        run_id="second-pause",
    )
    current = memory.append_message("user", "Return to the first topic.")

    built = context.build(stream="neutral", user_turn=current["turn"])

    assert built["inquiry"]["id"] == second["id"]
    assert [item["id"] for item in built["paused_inquiries"]] == [first["id"]]
    assert built["paused_inquiries"][0]["goal"] == "Understand the recurring work conflict"
    assert built["paused_inquiries"][0]["blocking_unknowns"][0]["id"] == "u1"
    assert built["budget"]["estimated_tokens"] <= built["budget"]["max_input_tokens"]


def test_controller_context_separates_user_evidence_from_assistant_continuity(
    migrated_db,
):
    user = memory.append_message("user", "I am increasingly disappointed.")
    memory.append_message("assistant", "The company has distorted your self-worth. " * 80)
    current = memory.append_message("user", "It is mostly internal disappointment.")

    built = context.build(stream="neutral", user_turn=current["turn"])

    assert [item["role"] for item in built["recent_messages"]] == ["user"]
    assert [item["role"] for item in built["assistant_context"]] == ["assistant"]
    assert built["recent_messages"][0]["turn"] == user["turn"]
    assert len(built["assistant_context"][0]["content"]) <= 601
    assert built["budget"]["dropped_assistant_messages"] == 0


def test_controller_context_exposes_recent_closed_episode_as_stale_checkpoint(
    migrated_db,
):
    old = memory.append_message("user", "I have lost confidence in the company.")
    ledger = {
        **_ledger(old["turn"], "lost confidence"),
        "frame": {
            "mode": "personal",
            "answer_scope": "bounded_guidance",
            "state_delta_required": False,
        },
        "current_state": [{
            "dimension": "belief",
            "text": "The user lacked confidence in the company.",
            "evidence": [{"turn": old["turn"], "quote": "lost confidence"}],
        }],
        "state_deltas": [],
    }
    episode = store.open_inquiry(
        stream="neutral", opened_turn=old["turn"], ledger=ledger,
        decision={}, run_id="episode-open",
    )
    store.apply_revision(
        inquiry_id=episode["id"], expected_revision=1, status="closed",
        ledger=ledger, action="close", user_turn=old["turn"], decision={},
        run_id="episode-close",
    )
    current = memory.append_message("user", "I want to revisit this now.")

    built = context.build(stream="neutral", user_turn=current["turn"])

    assert built["inquiry"] is None
    assert built["recent_episodes"][0]["id"] == episode["id"]
    assert built["recent_episodes"][0]["current_state"][0]["dimension"] == "belief"
    assert built["recent_episodes"][0]["stale_until_reconfirmed"] is True


def test_controller_context_exposes_prior_state_as_stale_not_as_user_evidence(
    migrated_db,
):
    old = memory.append_message("user", "I felt optimistic last week.")
    user_states.record(
        user_turn=old["turn"], stream="neutral",
        snapshot={
            "states": [{
                "dimension": "emotion",
                "text": "The user felt optimistic.",
                "evidence": [{"turn": old["turn"], "quote": "optimistic"}],
            }],
            "deltas": [],
        },
        inquiry_id=None, run_id="old-state",
    )
    current = memory.append_message("user", "A lot has changed since then.")

    built = context.build(stream="neutral", user_turn=current["turn"])

    assert built["prior_user_state"][0]["user_turn"] == old["turn"]
    assert built["prior_user_state"][0]["stale_until_reconfirmed"] is True
    assert old["turn"] not in {
        item["turn"] for item in built["cited_evidence"]
    }
