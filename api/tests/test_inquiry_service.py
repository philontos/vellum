import pytest

from app.inquiry import service, store
from app.inquiry.contracts import InquiryDecision
from app.store import memory


def _open_decision(turn: int, quote: str) -> InquiryDecision:
    return InquiryDecision.model_validate({
        "route": "inquire",
        "operation": "open",
        "expected_inquiry_id": None,
        "expected_revision": None,
        "patch": {
            "goal_update": {
                "text": "Decide whether to resign",
                "evidence": [{"turn": turn, "quote": quote}],
            },
            "add_interpretations": [{
                "text": "The manager may be targeting the user",
                "evidence": [{"turn": turn, "quote": "targeting me"}],
            }],
            "add_hypotheses": [
                {"text": "Selective pressure from the manager"},
                {"text": "Harsh but ordinary performance feedback"},
            ],
            "add_blocking_unknowns": [{
                "id": "u1",
                "question": "What concrete event happened most recently?",
                "why_material": "It distinguishes targeting from normal feedback.",
            }],
        },
        "next_question": "What concrete event happened most recently?",
        "target_unknown_id": "u1",
        "answer_brief": None,
        "provisional": False,
    })


def test_apply_decision_builds_a_grounded_ledger(migrated_db):
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )

    result = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral",
        user_turn=user["turn"],
        run_id="run-1",
    )

    assert result.inquiry["revision"] == 1
    assert result.inquiry["ledger"]["blocking_unknowns"][0]["status"] == "open"
    assert result.user_reply == "What concrete event happened most recently?"


@pytest.mark.parametrize(
    "turn,quote",
    [
        (999, "Should I resign?"),
        (0, "words that were never said"),
    ],
)
def test_apply_decision_rejects_missing_or_fabricated_evidence(
    migrated_db, turn, quote,
):
    memory.append_message("user", "My manager is targeting me. Should I resign?")

    with pytest.raises(service.EvidenceValidationError):
        service.apply_decision(
            _open_decision(turn, quote),
            stream="neutral",
            user_turn=0,
            run_id="run-1",
        )

    assert store.get_current("neutral") is None


def test_assistant_turn_cannot_be_used_as_user_evidence(migrated_db):
    assistant = memory.append_message("assistant", "Should I resign?")

    with pytest.raises(service.EvidenceValidationError):
        service.apply_decision(
            _open_decision(assistant["turn"], "Should I resign?"),
            stream="neutral",
            user_turn=assistant["turn"],
            run_id="run-1",
        )


def test_evidence_cannot_cross_persona_streams(migrated_db):
    other_stream = memory.append_message(
        "user", "My manager is targeting me. Should I resign?", stream="freud",
    )

    with pytest.raises(service.EvidenceValidationError):
        service.apply_decision(
            _open_decision(other_stream["turn"], "Should I resign?"),
            stream="neutral",
            user_turn=other_stream["turn"],
            run_id="run-1",
        )

    assert store.get_current("neutral") is None


def test_synthesis_with_open_unknowns_must_be_explicitly_provisional(migrated_db):
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    opened = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="run-1",
    ).inquiry
    decision = InquiryDecision.model_validate({
        "route": "synthesize",
        "operation": "update",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"],
        "patch": {},
        "next_question": None,
        "target_unknown_id": None,
        "answer_brief": "Answer while naming the missing event evidence.",
        "provisional": False,
    })

    with pytest.raises(service.NotReadyError):
        service.apply_decision(
            decision, stream="neutral", user_turn=user["turn"], run_id="run-2",
        )


def _followup(opened, question: str) -> InquiryDecision:
    return InquiryDecision.model_validate({
        "route": "inquire",
        "operation": "update",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"],
        "patch": {},
        "next_question": question,
        "target_unknown_id": "u1",
        "answer_brief": None,
        "provisional": False,
    })


def test_exact_question_repetition_is_rejected(migrated_db):
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    opened = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="run-1",
    ).inquiry

    with pytest.raises(service.RepeatedQuestionError):
        service.apply_decision(
            _followup(opened, "What concrete event happened most recently?"),
            stream="neutral", user_turn=user["turn"], run_id="run-2",
        )


def test_question_budget_forces_synthesis_or_pause(
    migrated_db, monkeypatch,
):
    monkeypatch.setenv("VELLUM_INQUIRY_MAX_QUESTIONS", "1")
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    opened = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="run-1",
    ).inquiry

    with pytest.raises(service.QuestionBudgetExceededError):
        service.apply_decision(
            _followup(opened, "Can you give a dated example?"),
            stream="neutral", user_turn=user["turn"], run_id="run-2",
        )


def test_ledger_has_a_hard_serialized_size_limit(migrated_db, monkeypatch):
    monkeypatch.setenv("VELLUM_INQUIRY_LEDGER_TOKENS", "20")
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )

    with pytest.raises(service.LedgerCapacityError):
        service.apply_decision(
            _open_decision(user["turn"], "Should I resign?"),
            stream="neutral", user_turn=user["turn"], run_id="run-1",
        )

    assert store.get_current("neutral") is None


def test_revisioned_decision_is_idempotent_by_run_id(migrated_db):
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    opened = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="run-1",
    ).inquiry
    decision = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "update",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"], "patch": {},
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Give a provisional answer.", "provisional": True,
    })

    first = service.apply_decision(
        decision, stream="neutral", user_turn=user["turn"], run_id="run-2",
    )
    replay = service.apply_decision(
        decision, stream="neutral", user_turn=user["turn"], run_id="run-2",
    )

    assert first.inquiry["revision"] == 2
    assert replay.inquiry["revision"] == 2
    assert len(store.list_events(opened["id"])) == 2


def test_topic_switch_can_pause_then_later_resume_for_synthesis(migrated_db):
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    opened = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="run-1",
    ).inquiry
    pause = InquiryDecision.model_validate({
        "route": "direct", "operation": "pause",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"], "patch": {},
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Answer the unrelated factual question.",
        "provisional": False,
    })

    paused = service.apply_decision(
        pause, stream="neutral", user_turn=user["turn"], run_id="run-2",
    ).inquiry
    assert paused["status"] == "paused"

    resume = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "resume",
        "expected_inquiry_id": paused["id"],
        "expected_revision": paused["revision"], "patch": {},
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Give a provisional synthesis.", "provisional": True,
    })
    resumed = service.apply_decision(
        resume, stream="neutral", user_turn=user["turn"], run_id="run-3",
    ).inquiry

    assert resumed["status"] == "reviewing"


def test_active_inquiry_synthesis_must_advance_its_revision(migrated_db):
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="run-1",
    )
    decision = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "none",
        "expected_inquiry_id": None,
        "expected_revision": None, "patch": {},
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Synthesize without recording state.",
        "provisional": True,
    })

    with pytest.raises(service.InvalidTransitionError):
        service.apply_decision(
            decision, stream="neutral", user_turn=user["turn"], run_id="run-2",
        )


def test_revision_lock_rejects_a_different_inquiry_with_the_same_revision(
    migrated_db,
):
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    opened = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="run-1",
    ).inquiry
    decision = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "update",
        "expected_inquiry_id": opened["id"] + 1,
        "expected_revision": opened["revision"], "patch": {},
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Do not apply this to another Inquiry.",
        "provisional": True,
    })

    with pytest.raises(store.RevisionConflictError):
        service.apply_decision(
            decision, stream="neutral", user_turn=user["turn"], run_id="run-2",
        )

    assert store.get(opened["id"])["revision"] == 1


def test_blocking_unknown_cannot_be_resolved_without_grounded_new_evidence(
    migrated_db,
):
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    opened = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="run-1",
    ).inquiry
    answer = memory.append_message("user", "I do not know what happened.")
    unsupported = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "update",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"],
        "patch": {"resolve_unknown_ids": ["u1"]},
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Synthesize from the answer.", "provisional": False,
    })

    with pytest.raises(service.UngroundedResolutionError):
        service.apply_decision(
            unsupported, stream="neutral", user_turn=answer["turn"],
            run_id="run-2",
        )

    assert store.get(opened["id"])["revision"] == 1

    grounded = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "close",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"],
        "patch": {
            "add_observations": [{
                "text": "The user cannot provide a concrete event.",
                "evidence": [{
                    "turn": answer["turn"],
                    "quote": "I do not know what happened",
                }],
            }],
            "resolve_unknown_ids": ["u1"],
        },
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Synthesize with explicit uncertainty.",
        "provisional": False,
    })
    result = service.apply_decision(
        grounded, stream="neutral", user_turn=answer["turn"], run_id="run-3",
    )

    assert result.inquiry["status"] == "closed"
    assert result.inquiry["ledger"]["blocking_unknowns"][0]["status"] == "resolved"


def test_close_can_be_staged_until_the_user_facing_answer_is_persisted(
    migrated_db,
):
    user = memory.append_message("user", "Please make the final decision.")
    opened = store.open_inquiry(
        stream="neutral", opened_turn=user["turn"],
        ledger={
            "goal": {"text": "Make a decision", "evidence": []},
            "observations": [], "interpretations": [], "hypotheses": [],
            "blocking_unknowns": [], "asked_questions": [],
            "provisional_conclusion": None,
        },
        decision={}, run_id="open",
    )
    close = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "close",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"], "patch": {},
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Deliver the final synthesis.", "provisional": False,
    })

    staged = service.apply_decision(
        close, stream="neutral", user_turn=user["turn"], run_id="answer",
        defer_close=True,
    )

    assert staged.close_pending is True
    assert staged.inquiry["status"] == "reviewing"
    finalized = service.finalize_deferred_close(
        staged, user_turn=user["turn"], run_id="answer:delivered",
    )
    assert finalized.close_pending is False
    assert finalized.inquiry["status"] == "closed"


def test_an_older_paused_inquiry_can_be_resumed_by_exact_id_and_revision(
    migrated_db,
):
    first = store.open_inquiry(
        stream="neutral", opened_turn=1,
        ledger={
            "goal": {"text": "first topic", "evidence": []},
            "observations": [], "interpretations": [], "hypotheses": [],
            "blocking_unknowns": [], "asked_questions": [],
            "provisional_conclusion": None,
        },
        decision={}, run_id="first-open",
    )
    first = store.apply_revision(
        inquiry_id=first["id"], expected_revision=1, status="paused",
        ledger=first["ledger"], action="pause", user_turn=2,
        decision={}, run_id="first-pause",
    )
    second = store.open_inquiry(
        stream="neutral", opened_turn=3,
        ledger={
            "goal": {"text": "second topic", "evidence": []},
            "observations": [], "interpretations": [], "hypotheses": [],
            "blocking_unknowns": [], "asked_questions": [],
            "provisional_conclusion": None,
        },
        decision={}, run_id="second-open",
    )
    store.apply_revision(
        inquiry_id=second["id"], expected_revision=1, status="paused",
        ledger=second["ledger"], action="pause", user_turn=4,
        decision={}, run_id="second-pause",
    )
    user = memory.append_message("user", "Return to the first topic.")
    resume = InquiryDecision.model_validate({
        "route": "synthesize", "operation": "resume",
        "expected_inquiry_id": first["id"],
        "expected_revision": first["revision"], "patch": {},
        "next_question": None, "target_unknown_id": None,
        "answer_brief": "Resume the first topic.", "provisional": False,
    })

    resumed = service.apply_decision(
        resume, stream="neutral", user_turn=user["turn"], run_id="resume-first",
    ).inquiry

    assert resumed["id"] == first["id"]
    assert resumed["status"] == "reviewing"
    assert store.get_active("neutral")["id"] == first["id"]
