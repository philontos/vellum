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
            "frame_update": {
                "mode": "practical",
                "answer_scope": "bounded_guidance",
                "state_delta_required": False,
            },
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
                "kind": "concrete_experience",
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


def test_new_inquiry_links_only_to_an_explicitly_related_closed_episode(
    migrated_db,
):
    old_ledger = service.empty_ledger()
    old_ledger["goal"] = {"text": "Understand the prior job", "evidence": []}
    old = store.open_inquiry(
        stream="neutral", opened_turn=0, ledger=old_ledger,
        decision={}, run_id="old-open",
    )
    old = store.apply_revision(
        inquiry_id=old["id"], expected_revision=old["revision"],
        status="closed", ledger=old_ledger, action="close", user_turn=0,
        decision={}, run_id="old-close",
    )
    user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )

    unrelated = service.apply_decision(
        _open_decision(user["turn"], "Should I resign?"),
        stream="neutral", user_turn=user["turn"], run_id="unrelated-open",
    ).inquiry

    assert unrelated["parent_inquiry_id"] is None
    store.apply_revision(
        inquiry_id=unrelated["id"], expected_revision=unrelated["revision"],
        status="closed", ledger=unrelated["ledger"], action="close",
        user_turn=user["turn"], decision={}, run_id="unrelated-close",
    )
    next_user = memory.append_message(
        "user", "My manager is targeting me. Should I resign?",
    )
    payload = _open_decision(
        next_user["turn"], "Should I resign?",
    ).model_dump(mode="json")
    payload["patch"]["frame_update"]["related_episode_id"] = old["id"]

    related = service.apply_decision(
        InquiryDecision.model_validate(payload), stream="neutral",
        user_turn=next_user["turn"], run_id="related-open",
    ).inquiry

    assert related["parent_inquiry_id"] == old["id"]


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
        "synthesis_basis": "ready",
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
        "synthesis_basis": "user_requested_provisional",
        "synthesis_basis_evidence": [{
            "turn": user["turn"], "quote": "Should I resign?",
        }],
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
        "synthesis_basis": "user_requested_provisional",
        "synthesis_basis_evidence": [{
            "turn": user["turn"], "quote": "Should I resign?",
        }],
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
        "synthesis_basis": "user_requested_provisional",
        "synthesis_basis_evidence": [{
            "turn": user["turn"], "quote": "Should I resign?",
        }],
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
        "synthesis_basis": "user_requested_provisional",
        "synthesis_basis_evidence": [{
            "turn": user["turn"], "quote": "Should I resign?",
        }],
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
        "synthesis_basis": "ready",
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
                "kind": "other",
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
        "synthesis_basis": "ready",
    })
    result = service.apply_decision(
        grounded, stream="neutral", user_turn=answer["turn"], run_id="run-3",
    )

    assert result.inquiry["status"] == "closed"
    assert result.inquiry["ledger"]["blocking_unknowns"][0]["status"] == "resolved"


def test_personal_inquiry_cannot_close_on_state_only_without_concrete_experience(
    migrated_db,
):
    first = memory.append_message(
        "user",
        "Should I watch outside opportunities? I am losing confidence in the company.",
    )
    ledger = {
        "frame": {
            "mode": "personal",
            "answer_scope": "bounded_guidance",
            "state_delta_required": True,
        },
        "goal": {
            "text": "Decide whether to watch outside opportunities.",
            "evidence": [{"turn": first["turn"], "quote": "outside opportunities"}],
        },
        "current_state": [{
            "dimension": "belief",
            "text": "The user is losing confidence in the company.",
            "evidence": [{"turn": first["turn"], "quote": "losing confidence"}],
        }],
        "state_deltas": [{
            "dimension": "belief",
            "text": "Confidence is declining.",
            "reference": "unspecified_past",
            "evidence": [{"turn": first["turn"], "quote": "losing confidence"}],
        }],
        "observations": [],
        "interpretations": [],
        "hypotheses": [],
        "blocking_unknowns": [{
            "id": "u1", "kind": "orientation",
            "question": "Is the concern external or internal?",
            "why_material": "It locates the concern.",
            "status": "open", "resolved_after_turn": None,
        }],
        "asked_questions": [],
        "provisional_conclusion": None,
    }
    opened = store.open_inquiry(
        stream="neutral", opened_turn=first["turn"], ledger=ledger,
        decision={}, run_id="open",
    )
    answer = memory.append_message("user", "It is disappointment with this company.")
    close = InquiryDecision.model_validate({
        "route": "synthesize",
        "operation": "close",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"],
        "patch": {"resolve_unknown_ids": ["u1"]},
        "user_state": {
            "states": [{
                "dimension": "emotion",
                "text": "The user is disappointed with the company.",
                "evidence": [{
                    "turn": answer["turn"],
                    "quote": "disappointment with this company",
                }],
            }],
            "deltas": [],
        },
        "answer_brief": "Explain why watching opportunities is correct.",
        "context_mode": "recent",
        "provisional": False,
        "synthesis_basis": "ready",
    })

    with pytest.raises(service.NotReadyError, match="concrete experience"):
        service.apply_decision(
            close, stream="neutral", user_turn=answer["turn"], run_id="close",
        )

    assert store.get(opened["id"])["revision"] == 1


def test_latest_user_state_replaces_older_state_in_the_same_dimension(
    migrated_db,
):
    ledger = service.empty_ledger()
    ledger["current_state"] = [{
        "dimension": "belief",
        "text": "The user still trusts the company.",
        "evidence": [{"turn": 0, "quote": "I still trust it"}],
    }]
    ledger["blocking_unknowns"] = [{
        "id": "u1",
        "kind": "state_delta",
        "question": "What changed that trust?",
        "why_material": "The change is the current topic.",
        "status": "open",
        "resolved_after_turn": None,
    }]
    decision = InquiryDecision.model_validate({
        "route": "inquire",
        "operation": "update",
        "expected_inquiry_id": 1,
        "expected_revision": 1,
        "patch": {},
        "user_state": {
            "states": [{
                "dimension": "belief",
                "text": "The user no longer trusts the company.",
                "evidence": [{"turn": 2, "quote": "I no longer trust it"}],
            }],
            "deltas": [],
        },
        "next_question": "What changed that trust?",
        "target_unknown_id": "u1",
        "answer_brief": None,
        "provisional": False,
    })

    updated = service._apply_patch(ledger, decision, user_turn=2)

    assert updated["current_state"] == [{
        "dimension": "belief",
        "text": "The user no longer trusts the company.",
        "evidence": [{"turn": 2, "quote": "I no longer trust it"}],
    }]


def test_provisional_synthesis_cannot_use_question_budget_before_it_is_exhausted(
    migrated_db,
):
    ledger = service.empty_ledger()
    ledger["blocking_unknowns"] = [{
        "id": "u1", "kind": "concrete_experience",
        "question": "What happened?", "why_material": "It matters.",
        "status": "open", "resolved_after_turn": None,
    }]
    opened = store.open_inquiry(
        stream="neutral", opened_turn=0, ledger=ledger,
        decision={"route": "inquire"}, run_id="open-budget",
    )
    decision = InquiryDecision.model_validate({
        "route": "synthesize",
        "operation": "update",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"],
        "patch": {},
        "answer_brief": "Answer with explicit uncertainty.",
        "provisional": True,
        "synthesis_basis": "question_budget_exhausted",
        "synthesis_basis_evidence": [],
    })

    with pytest.raises(service.NotReadyError, match="question budget"):
        service.apply_decision(
            decision, stream="neutral", user_turn=0, run_id="premature",
        )


def test_controller_cannot_downgrade_the_answer_scope_to_evade_readiness(
    migrated_db,
):
    ledger = service.empty_ledger()
    ledger["frame"] = {
        "mode": "personal",
        "answer_scope": "causal_judgment",
        "state_delta_required": True,
        "related_episode_id": None,
    }
    ledger["blocking_unknowns"] = [{
        "id": "u1", "kind": "concrete_experience",
        "question": "What happened?", "why_material": "Causality needs it.",
        "status": "open", "resolved_after_turn": None,
    }]
    opened = store.open_inquiry(
        stream="neutral", opened_turn=0, ledger=ledger,
        decision={}, run_id="scope-open",
    )
    decision = InquiryDecision.model_validate({
        "route": "inquire",
        "operation": "update",
        "expected_inquiry_id": opened["id"],
        "expected_revision": opened["revision"],
        "patch": {
            "frame_update": {
                "mode": "personal",
                "answer_scope": "bounded_guidance",
                "state_delta_required": False,
                "related_episode_id": None,
            },
        },
        "next_question": "What happened?",
        "target_unknown_id": "u1",
        "answer_brief": None,
        "provisional": False,
    })

    with pytest.raises(service.NotReadyError, match="answer scope"):
        service.apply_decision(
            decision, stream="neutral", user_turn=0, run_id="scope-downgrade",
        )


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
        "synthesis_basis": "ready",
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
        "synthesis_basis": "ready",
    })

    resumed = service.apply_decision(
        resume, stream="neutral", user_turn=user["turn"], run_id="resume-first",
    ).inquiry

    assert resumed["id"] == first["id"]
    assert resumed["status"] == "reviewing"
    assert store.get_active("neutral")["id"] == first["id"]
