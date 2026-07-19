import json

import pytest

from app.chat import orchestrator
from app.inquiry import store
from app.inquiry.contracts import InquiryDecision
from app.llm import client as llm_client
from app.store import memory, traces, turn_runs


async def _no_embed(text):
    return [1.0, 0.0, 0.0]


def _direct(brief="Answer directly."):
    return InquiryDecision.model_validate({
        "route": "direct", "operation": "none", "expected_revision": None,
        "patch": {}, "next_question": None, "target_unknown_id": None,
        "answer_brief": brief, "provisional": False,
    })


@pytest.mark.asyncio
async def test_inquire_path_returns_validated_question_without_responder(
    migrated_db, monkeypatch,
):
    monkeypatch.setattr(orchestrator.ingest, "embed", _no_embed)

    async def decide(ctx):
        llm_client._record_llm_call({
            "stage": "inquiry.decide", "model": "controller-model",
            "prompt_chars": 100, "prompt_tokens": 20,
            "completion_tokens": 5, "total_tokens": 25,
            "duration_ms": 12, "context": {"stream": "neutral"},
            "status": "ok", "system_prompt": "controller system",
            "user_prompt": "controller input", "response": "{}",
            "reasoning": None,
        })
        turn = ctx["current_user_turn"]["turn"]
        return InquiryDecision.model_validate({
            "route": "inquire", "operation": "open",
            "expected_revision": None,
            "patch": {
                "goal_update": {
                    "text": "Decide whether to resign",
                    "evidence": [{"turn": turn, "quote": "Should I resign?"}],
                },
                "add_blocking_unknowns": [{
                    "id": "u1", "question": "What happened most recently?",
                    "why_material": "A concrete event changes the judgment.",
                }],
            },
            "next_question": "What happened most recently?",
            "target_unknown_id": "u1", "answer_brief": None,
            "provisional": False,
        })

    async def responder_must_not_run(*args, **kwargs):
        raise AssertionError("Responder must not run for an inquiry question")
        yield

    monkeypatch.setattr(orchestrator.controller, "decide", decide)
    monkeypatch.setattr(orchestrator.respond, "stream", responder_must_not_run)
    monkeypatch.setattr(orchestrator, "schedule_background", lambda: None)

    events = [event async for event in orchestrator.turn_events(
        "Should I resign?", persona_name="neutral",
    )]

    final = next(event for event in events if event["type"] == "final")
    assert final["content"] == "What happened most recently?"
    assert final["route"] == "inquire"
    assert store.get_current("neutral")["revision"] == 1
    assert memory.recent_tail(1)[0]["content"] == "What happened most recently?"

    run = turn_runs.list_recent()[0]
    assert run["id"] == final["run_id"]
    assert run["route"] == "inquire"
    assert run["status"] == "done"
    assert run["revision_before"] is None
    assert run["revision_after"] == 1
    assert run["controller_model"] == "controller-model"
    assert run["responder_model"] is None
    spans = [row for row in traces.list_recent() if row["run_id"] == run["id"]]
    assert {span["stage"] for span in spans} == {"inquiry.decide", "chat"}
    assert [
        span["stage"] for span in sorted(spans, key=lambda item: item["id"])
    ] == ["inquiry.decide", "chat"]
    assert next(span for span in spans if span["stage"] == "inquiry.decide")[
        "scenario"
    ] == "inquiry"


@pytest.mark.asyncio
async def test_direct_path_injects_plan_and_streams_responder(
    migrated_db, monkeypatch,
):
    monkeypatch.setattr(orchestrator.ingest, "embed", _no_embed)
    monkeypatch.setattr(orchestrator.controller, "decide", lambda ctx: _async(_direct(
        "Explain the arithmetic without personal analysis.",
    )))

    async def messages(**kwargs):
        return [
            {"role": "system", "content": (
                "BASE\n\n" + "\n\n".join(kwargs["extra_system_sections"])
            )},
            {"role": "user", "content": "What is 2+2?"},
        ]

    seen = {}

    async def response_stream(payload, **kwargs):
        seen["messages"] = payload
        yield {"type": "delta", "text": "Four"}
        yield {
            "type": "final", "content": "Four", "reasoning": None,
            "tool_calls": None, "prompt_tokens": 5, "completion_tokens": 1,
            "duration_ms": 10,
        }

    monkeypatch.setattr(orchestrator.assemble, "build_messages", messages)
    monkeypatch.setattr(orchestrator.respond, "stream", response_stream)
    monkeypatch.setattr(orchestrator, "schedule_background", lambda: None)

    events = [event async for event in orchestrator.turn_events(
        "What is 2+2?", persona_name="neutral",
    )]

    assert [event["text"] for event in events if event["type"] == "delta"] == ["Four"]
    assert "## Validated turn plan" in seen["messages"][0]["content"]
    assert "without personal analysis" in seen["messages"][0]["content"]
    assert memory.recent_tail(1)[0]["content"] == "Four"


@pytest.mark.asyncio
async def test_low_information_direct_turn_forces_minimal_responder_context(
    migrated_db, monkeypatch,
):
    monkeypatch.setattr(orchestrator.ingest, "embed", _no_embed)
    decision = InquiryDecision.model_validate({
        "route": "direct",
        "operation": "none",
        "patch": {},
        "answer_brief": "Reply with a brief greeting.",
        "context_mode": "personal",
        "provisional": False,
    })
    decision.note_normalized_fields(["patch"])
    monkeypatch.setattr(
        orchestrator.controller, "decide", lambda ctx: _async(decision),
    )
    seen = {}
    response_seen = {}

    async def messages(**kwargs):
        seen.update(kwargs)
        return orchestrator.assemble.AssembledMessages(
            [{"role": "system", "content": kwargs["extra_system_sections"][0]},
             {"role": "user", "content": "hello"}],
            meta={
                "context_mode": kwargs["context_mode"],
                "estimated_tokens": 200,
                "max_input_tokens": 8000,
                "dropped_history_messages": 4,
                "history_turns": [0],
            },
        )

    async def response_stream(payload, **kwargs):
        response_seen.update(kwargs)
        yield {"type": "delta", "text": "Hi."}
        yield {
            "type": "final", "content": "Hi.", "reasoning": None,
            "tool_calls": None, "prompt_tokens": 100,
            "completion_tokens": 2, "duration_ms": 5,
        }

    monkeypatch.setattr(orchestrator.assemble, "build_messages", messages)
    monkeypatch.setattr(orchestrator.respond, "stream", response_stream)
    monkeypatch.setattr(orchestrator, "schedule_background", lambda: None)

    events = [event async for event in orchestrator.turn_events(
        "hello", persona_name="neutral",
    )]

    assert events[-1]["content"] == "Hi."
    assert seen["context_mode"] == "minimal"
    assert seen["exclude_recall_through_turn"] == -1
    assert response_seen["through_turn"] == -1
    assert response_seen["exclude_recall_turns"] == {0}
    assert response_seen["recall_summary_mode"] == "digest"
    assert response_seen["recall_enabled"] is False
    run = turn_runs.list_recent()[0]
    assert run["context_meta"]["responder"]["context_mode"] == "minimal"
    assert run["context_meta"]["controller_normalized_fields"] == ["patch"]
    chat_span = next(
        row for row in traces.list_recent() if row["run_id"] == run["id"]
    )
    params = json.loads(chat_span["params"])
    assert params["context"]["context_mode"] == "minimal"
    assert params["controller_normalized_fields"] == ["patch"]


@pytest.mark.asyncio
async def test_controller_failure_does_not_mutate_ledger_and_uses_cautious_responder(
    migrated_db, monkeypatch,
):
    monkeypatch.setattr(orchestrator.ingest, "embed", _no_embed)

    async def fail(_context):
        raise RuntimeError("controller unavailable")

    context_seen = {}

    async def messages(**kwargs):
        context_seen.update(kwargs)
        return [{"role": "system", "content": (
            "BASE\n\n" + "\n\n".join(kwargs["extra_system_sections"])
        )}]

    seen = {}

    async def response_stream(payload, **kwargs):
        seen["system"] = payload[0]["content"]
        yield {"type": "delta", "text": "Could you share one concrete example?"}
        yield {
            "type": "final", "content": "Could you share one concrete example?",
            "reasoning": None, "tool_calls": None, "prompt_tokens": None,
            "completion_tokens": None, "duration_ms": 1,
        }

    monkeypatch.setattr(orchestrator.controller, "decide", fail)
    monkeypatch.setattr(orchestrator.assemble, "build_messages", messages)
    monkeypatch.setattr(orchestrator.respond, "stream", response_stream)
    monkeypatch.setattr(orchestrator, "schedule_background", lambda: None)

    events = [event async for event in orchestrator.turn_events(
        "My manager is targeting me.", persona_name="neutral",
    )]

    assert events[-1]["type"] == "final"
    assert "avoid unsupported conclusions" in seen["system"]
    assert context_seen["context_mode"] == "recent"
    assert context_seen["recall_query"] is None
    assert store.get_current("neutral") is None
    run = turn_runs.list_recent()[0]
    assert run["status"] == "degraded"
    assert "controller unavailable" in run["error"]


@pytest.mark.asyncio
async def test_responder_failure_marks_the_root_run_as_error(
    migrated_db, monkeypatch,
):
    monkeypatch.setattr(orchestrator.ingest, "embed", _no_embed)

    async def decide(_ctx):
        llm_client._record_llm_call({
            "stage": "inquiry.decide", "model": "controller-model",
            "prompt_chars": 100, "prompt_tokens": 20,
            "completion_tokens": 5, "total_tokens": 25,
            "duration_ms": 12, "context": {}, "status": "ok",
            "system_prompt": "controller system",
            "user_prompt": "controller input", "response": "{}",
            "reasoning": None,
        })
        return _direct()

    monkeypatch.setattr(orchestrator.controller, "decide", decide)

    async def messages(**kwargs):
        return [{"role": "system", "content": "BASE"}]

    async def response_stream(*args, **kwargs):
        raise RuntimeError("responder unavailable")
        yield

    monkeypatch.setattr(orchestrator.assemble, "build_messages", messages)
    monkeypatch.setattr(orchestrator.respond, "stream", response_stream)
    monkeypatch.setattr(orchestrator, "schedule_background", lambda: None)

    with pytest.raises(RuntimeError, match="responder unavailable"):
        _ = [event async for event in orchestrator.turn_events(
            "Please answer.", persona_name="neutral",
        )]

    run = turn_runs.list_recent()[0]
    assert run["status"] == "error"
    assert "responder unavailable" in run["error"]
    spans = [row for row in traces.list_recent() if row["run_id"] == run["id"]]
    assert [(span["stage"], span["turn"]) for span in spans] == [
        ("inquiry.decide", run["user_turn"]),
    ]


@pytest.mark.asyncio
async def test_failed_synthesis_keeps_a_close_pending_inquiry_retryable(
    migrated_db, monkeypatch,
):
    monkeypatch.setattr(orchestrator.ingest, "embed", _no_embed)
    initial = memory.append_message("user", "I am ready for the answer.")
    opened = store.open_inquiry(
        stream="neutral", opened_turn=initial["turn"],
        ledger={
            "goal": {"text": "Reach a decision", "evidence": []},
            "observations": [], "interpretations": [], "hypotheses": [],
            "blocking_unknowns": [], "asked_questions": [],
            "provisional_conclusion": None,
        },
        decision={}, run_id="initial-open",
    )

    async def decide(_ctx):
        return InquiryDecision.model_validate({
            "route": "synthesize", "operation": "close",
            "expected_inquiry_id": opened["id"],
            "expected_revision": opened["revision"], "patch": {},
            "next_question": None, "target_unknown_id": None,
            "answer_brief": "Deliver the final answer.", "provisional": False,
        })

    async def messages(**kwargs):
        return [{"role": "system", "content": "BASE"}]

    async def response_stream(*args, **kwargs):
        raise RuntimeError("responder unavailable")
        yield

    monkeypatch.setattr(orchestrator.controller, "decide", decide)
    monkeypatch.setattr(orchestrator.assemble, "build_messages", messages)
    monkeypatch.setattr(orchestrator.respond, "stream", response_stream)
    monkeypatch.setattr(orchestrator, "schedule_background", lambda: None)

    with pytest.raises(RuntimeError, match="responder unavailable"):
        _ = [event async for event in orchestrator.turn_events(
            "Please give me the answer.", persona_name="neutral",
        )]

    retryable = store.get(opened["id"])
    assert retryable["status"] == "reviewing"
    assert retryable["revision"] == 2


@pytest.mark.asyncio
async def test_revision_conflict_refreshes_ledger_and_retries_controller_once(
    migrated_db, monkeypatch,
):
    monkeypatch.setattr(orchestrator.ingest, "embed", _no_embed)
    initial = memory.append_message("user", "I am weighing a job change.")
    ledger = {
        "goal": {"text": "Decide whether to change jobs", "evidence": []},
        "observations": [], "interpretations": [], "hypotheses": [],
        "blocking_unknowns": [], "asked_questions": [],
        "provisional_conclusion": None,
    }
    opened = store.open_inquiry(
        stream="neutral", opened_turn=initial["turn"], ledger=ledger,
        decision={}, run_id="initial-open",
    )
    revisions = []

    async def decide(ctx):
        revision = ctx["inquiry"]["revision"]
        revisions.append(revision)
        if len(revisions) == 1:
            store.apply_revision(
                inquiry_id=opened["id"], expected_revision=1,
                status="exploring", ledger=ledger, action="inquire",
                user_turn=ctx["current_user_turn"]["turn"], decision={},
                run_id="concurrent-run",
            )
        return InquiryDecision.model_validate({
            "route": "synthesize", "operation": "update",
            "expected_inquiry_id": ctx["inquiry"]["id"],
            "expected_revision": revision, "patch": {},
            "next_question": None, "target_unknown_id": None,
            "answer_brief": "Synthesize from the refreshed Ledger.",
            "provisional": False,
        })

    async def messages(**kwargs):
        return [{"role": "system", "content": "BASE"}]

    async def response_stream(*args, **kwargs):
        yield {"type": "delta", "text": "Use the refreshed evidence."}
        yield {
            "type": "final", "content": "Use the refreshed evidence.",
            "reasoning": None, "tool_calls": None, "prompt_tokens": 4,
            "completion_tokens": 2, "duration_ms": 5,
        }

    monkeypatch.setattr(orchestrator.controller, "decide", decide)
    monkeypatch.setattr(orchestrator.assemble, "build_messages", messages)
    monkeypatch.setattr(orchestrator.respond, "stream", response_stream)
    monkeypatch.setattr(orchestrator, "schedule_background", lambda: None)

    events = [event async for event in orchestrator.turn_events(
        "I have enough information now.", persona_name="neutral",
    )]

    assert revisions == [1, 2]
    assert events[-1]["route"] == "synthesize"
    run = turn_runs.list_recent()[0]
    assert run["status"] == "done"
    assert run["revision_before"] == 1
    assert run["revision_after"] == 3
    assert run["error"] is None


@pytest.mark.asyncio
async def test_concurrent_open_refreshes_into_the_new_inquiry_instead_of_degrading(
    migrated_db, monkeypatch,
):
    monkeypatch.setattr(orchestrator.ingest, "embed", _no_embed)
    seen_inquiries = []

    async def decide(ctx):
        seen_inquiries.append(ctx["inquiry"])
        turn = ctx["current_user_turn"]["turn"]
        if ctx["inquiry"] is None:
            store.open_inquiry(
                stream="neutral", opened_turn=turn,
                ledger={
                    "goal": {"text": "Concurrent topic", "evidence": []},
                    "observations": [], "interpretations": [],
                    "hypotheses": [], "blocking_unknowns": [],
                    "asked_questions": [], "provisional_conclusion": None,
                },
                decision={}, run_id="concurrent-open",
            )
            return InquiryDecision.model_validate({
                "route": "inquire", "operation": "open",
                "expected_inquiry_id": None, "expected_revision": None,
                "patch": {
                    "goal_update": {
                        "text": "Decide the concurrent topic",
                        "evidence": [{"turn": turn, "quote": "Help me decide"}],
                    },
                    "add_blocking_unknowns": [{
                        "id": "u1", "question": "What matters most?",
                        "why_material": "It changes the decision.",
                    }],
                },
                "next_question": "What matters most?",
                "target_unknown_id": "u1", "answer_brief": None,
                "provisional": False,
            })
        return InquiryDecision.model_validate({
            "route": "synthesize", "operation": "close",
            "expected_inquiry_id": ctx["inquiry"]["id"],
            "expected_revision": ctx["inquiry"]["revision"], "patch": {},
            "next_question": None, "target_unknown_id": None,
            "answer_brief": "Answer using the refreshed Inquiry.",
            "provisional": False,
        })

    async def messages(**kwargs):
        return [{"role": "system", "content": "BASE"}]

    async def response_stream(*args, **kwargs):
        yield {"type": "delta", "text": "Refreshed answer."}
        yield {
            "type": "final", "content": "Refreshed answer.",
            "reasoning": None, "tool_calls": None, "prompt_tokens": 4,
            "completion_tokens": 2, "duration_ms": 5,
        }

    monkeypatch.setattr(orchestrator.controller, "decide", decide)
    monkeypatch.setattr(orchestrator.assemble, "build_messages", messages)
    monkeypatch.setattr(orchestrator.respond, "stream", response_stream)
    monkeypatch.setattr(orchestrator, "schedule_background", lambda: None)

    events = [event async for event in orchestrator.turn_events(
        "Help me decide this concurrent topic.", persona_name="neutral",
    )]

    assert [item is None for item in seen_inquiries] == [True, False]
    assert events[-1]["route"] == "synthesize"
    run = turn_runs.list_recent()[0]
    assert run["status"] == "done"
    assert run["revision_before"] is None
    assert run["revision_after"] == 3
    assert store.get(run["inquiry_id"])["status"] == "closed"


async def _async(value):
    return value
