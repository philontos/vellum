import json

from app.inquiry import budget, context, store
from app.store import memory, model


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
    assert any(
        item["turn"] == old["turn"] and "first conflict" in item["content"]
        for item in built["cited_evidence"]
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
