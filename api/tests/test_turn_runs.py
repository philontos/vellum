from app.chat.run_observer import _context_meta
from app.store import traces, turn_runs


def test_controller_context_meta_exposes_budget_and_question_pressure():
    context = {
        "inquiry": {"id": 2},
        "recent_messages": [{"turn": 1}],
        "cited_evidence": [{"turn": 2}],
        "paused_inquiries": [{"id": 1}],
        "policy": {
            "max_questions": 5,
            "questions_asked": 4,
            "remaining_questions": 1,
        },
        "budget": {
            "estimated_tokens": 900,
            "max_input_tokens": 1_000,
            "dropped_recent_messages": 2,
            "dropped_cited_evidence": 3,
            "dropped_paused_inquiries": 1,
            "current_user_turn_truncated": True,
        },
    }

    assert _context_meta(context) == {
        "estimated_tokens": 900,
        "max_input_tokens": 1_000,
        "dropped_recent_messages": 2,
        "dropped_cited_evidence": 3,
        "dropped_paused_inquiries": 1,
        "current_user_turn_truncated": True,
        "recent_message_count": 1,
        "cited_evidence_count": 1,
        "paused_inquiry_count": 1,
        "had_active_inquiry": True,
        "max_questions": 5,
        "questions_asked": 4,
        "remaining_questions": 1,
    }


def test_turn_run_tracks_the_pipeline_root_and_correlated_spans(migrated_db):
    turn_runs.start(
        run_id="run-1", user_turn=4, stream="neutral",
        context_meta={"estimated_tokens": 1200, "dropped_recent_messages": 2},
        prompt_release_id=7, prompt_release_version=3,
    )
    trace_id = traces.record(
        turn=5, stage="inquiry.decide", scenario="inquiry", run_id="run-1",
        attempt=1, model="glm", params={}, prompt="p", output="{}",
        prompt_tokens=10, completion_tokens=2, duration_ms=30,
    )
    turn_runs.finish(
        run_id="run-1", assistant_turn=5, route="inquire", status="done",
        inquiry_id=2, revision_before=None, revision_after=1,
        controller_model="glm", responder_model=None,
        decision={"route": "inquire"}, error=None,
    )

    item = turn_runs.get("run-1")
    assert item["route"] == "inquire"
    assert item["context_meta"]["dropped_recent_messages"] == 2
    assert item["decision"] == {"route": "inquire"}
    assert "decision_json" not in item
    assert item["inquiry_id"] == 2

    span = traces.get_by_id(trace_id)
    assert span["run_id"] == "run-1"
    assert span["scenario"] == "inquiry"
    assert span["attempt"] == 1


def test_failed_turn_run_keeps_the_error_without_claiming_completion(migrated_db):
    turn_runs.start(
        run_id="run-2", user_turn=8, stream="neutral", context_meta={},
        prompt_release_id=None, prompt_release_version=None,
    )
    turn_runs.fail("run-2", "Controller timed out")

    item = turn_runs.get("run-2")
    assert item["status"] == "error"
    assert item["assistant_turn"] is None
    assert item["error"] == "Controller timed out"
    assert item["decision"] is None
    assert "decision_json" not in item
