"""Pure-code workflow for one user turn.

The orchestrator owns persistence, routing, validation, streaming, and background
handoff. Semantic decisions remain in the Inquiry Controller and final prose in
the Chat Responder.
"""
import asyncio
import json
import uuid

from app import config
from app.chat import (
    assemble, context_plan, ingest, persona, respond, run_observer, turn_guidance,
)
from app.inquiry import context as inquiry_context
from app.inquiry import controller, service, store as inquiry_store
from app.inquiry.contracts import InquiryDecision
from app.llm.client import resolve_structured_llm_config
from app.model_loop import runner
from app.prompts import runtime
from app.store import traces, user_states


_background_tasks: set[asyncio.Task] = set()


def _track(task: asyncio.Task) -> None:
    _background_tasks.add(task)

    def _done(finished: asyncio.Task) -> None:
        _background_tasks.discard(finished)
        if not finished.cancelled() and finished.exception() is not None:
            import traceback
            traceback.print_exception(finished.exception())

    task.add_done_callback(_done)


def schedule_background() -> None:
    _track(asyncio.create_task(runner.run_pending()))


def _fallback_decision() -> InquiryDecision:
    return InquiryDecision.model_validate({
        "route": "direct",
        "operation": "none",
        "expected_inquiry_id": None,
        "expected_revision": None,
        "patch": {},
        "next_question": None,
        "target_unknown_id": None,
        "answer_brief": (
            "Respond cautiously. Avoid unsupported conclusions and, only if "
            "user-specific information is material, ask one brief question."
        ),
        "context_mode": "recent",
        "recall_query": None,
        "provisional": True,
    })


def _trace(
    *, assistant_turn: int, stream: str, run_id: str,
    snapshot: runtime.PromptSnapshot, applied: service.AppliedDecision,
    model: str | None, prompt: object, output: str, final: dict,
    controller_error: str | None,
    context_meta: dict | None, pipeline_sequence: int,
    normalized_fields: tuple[str, ...],
) -> None:
    inquiry = applied.inquiry
    traces.record(
        turn=assistant_turn,
        stage="chat",
        model=model,
        params={
            "persona": stream,
            "run_id": run_id,
            "route": applied.decision.route,
            "inquiry_id": inquiry["id"] if inquiry is not None else None,
            "inquiry_revision": inquiry["revision"] if inquiry is not None else None,
            "controller_error": controller_error,
            "prompt_release_id": snapshot.release_id,
            "prompt_release_version": snapshot.release_version,
            "pipeline_sequence": pipeline_sequence,
            "context": context_meta or {},
            "controller_normalized_fields": list(normalized_fields),
        },
        prompt=json.dumps(prompt, ensure_ascii=False),
        output=output,
        reasoning=final.get("reasoning"),
        tool_calls=final.get("tool_calls"),
        prompt_tokens=final.get("prompt_tokens"),
        completion_tokens=final.get("completion_tokens"),
        duration_ms=final.get("duration_ms"),
        run_id=run_id,
        scenario=(
            "inquiry" if applied.decision.route == "inquire" else "chat"
        ),
        attempt=1,
    )


async def turn_events(text: str, persona_name: str | None = None):
    """Yield the existing chat event contract and persist one complete round."""
    with runtime.ensure_snapshot() as snapshot:
        stream = (
            persona_name if persona_name in persona.available()
            else config.persona_name()
        )
        run_id = uuid.uuid4().hex
        user = await ingest.persist_user(text, stream=stream)
        control_context = inquiry_context.build(
            stream=stream, user_turn=user["turn"],
        )
        controller_cfg = resolve_structured_llm_config(scenario="inquiry")
        observer = run_observer.TurnRunObserver.start(
            run_id=run_id,
            user_turn=user["turn"],
            stream=stream,
            context=control_context,
            prompt_release_id=snapshot.release_id,
            prompt_release_version=snapshot.release_version,
            controller_model=controller_cfg.get("model"),
        )

        try:
            async for event in _execute_turn(
                text=text,
                stream=stream,
                user_turn=user["turn"],
                run_id=run_id,
                snapshot=snapshot,
                control_context=control_context,
                observer=observer,
            ):
                yield event
        except Exception as exc:
            observer.fail(exc)
            raise


async def _execute_turn(
    *, text: str, stream: str, user_turn: int, run_id: str,
    snapshot: runtime.PromptSnapshot, control_context: dict,
    observer: run_observer.TurnRunObserver,
):
    controller_error = None
    effective_control_context = control_context
    try:
        with observer.capture_controller():
            decision = await controller.decide(effective_control_context)
        try:
            applied = service.apply_decision(
                decision, stream=stream, user_turn=user_turn, run_id=run_id,
                defer_close=True,
            )
        except (
            inquiry_store.RevisionConflictError,
            inquiry_store.ActiveInquiryExistsError,
        ):
            # Another turn advanced the Ledger after this controller snapshot.
            # Refresh once; repeated contention then follows the normal cautious
            # degradation path instead of overwriting newer evidence.
            effective_control_context = inquiry_context.build(
                stream=stream, user_turn=user_turn,
            )
            with observer.capture_controller():
                decision = await controller.decide(effective_control_context)
            applied = service.apply_decision(
                decision, stream=stream, user_turn=user_turn, run_id=run_id,
                defer_close=True,
            )
    except Exception as exc:
        # Critical state fails closed: no mutation survives a failed service
        # validation. Availability degrades to a cautious responder turn.
        controller_error = f"{type(exc).__name__}: {exc}"[:500]
        decision = _fallback_decision()
        applied = service.apply_decision(
            decision, stream=stream, user_turn=user_turn, run_id=None,
        )

    user_states.record(
        user_turn=user_turn,
        stream=stream,
        snapshot=applied.decision.user_state.model_dump(mode="json"),
        inquiry_id=(applied.inquiry or {}).get("id"),
        run_id=run_id,
    )

    observer.note_decision(applied.decision)

    if applied.user_reply is not None:
        final = {
            "type": "final",
            "content": applied.user_reply,
            "reasoning": None,
            "tool_calls": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "duration_ms": None,
            "route": decision.route,
            "run_id": run_id,
        }
        assistant = ingest.persist_assistant(applied.user_reply, stream=stream)
        observer.persist_controller_spans(assistant["turn"])
        cfg = resolve_structured_llm_config(scenario="inquiry")
        _trace(
            assistant_turn=assistant["turn"], stream=stream, run_id=run_id,
            snapshot=snapshot, applied=applied, model=cfg.get("model"),
            prompt=effective_control_context, output=applied.user_reply, final=final,
            controller_error=controller_error,
            context_meta=None,
            pipeline_sequence=observer.chat_pipeline_sequence(),
            normalized_fields=observer.controller_normalized_fields,
        )
        observer.complete(
            assistant_turn=assistant["turn"], applied=applied,
            responder_model=None, controller_error=controller_error,
        )
        schedule_background()
        yield {"type": "delta", "text": applied.user_reply}
        yield final
        return

    responder_mode = context_plan.effective_mode(applied.decision, text)
    messages = await assemble.build_messages(
        query=text,
        persona_name=stream,
        context_mode=responder_mode,
        recall_query=applied.decision.recall_query,
        extra_system_sections=[turn_guidance.render(
            applied, controller_error=controller_error,
        )],
        exclude_recall_through_turn=user_turn - 1,
    )
    recall_tool_enabled = (
        responder_mode == "personal"
        and config.response_recall_tokens() > 0
    )
    response_context_meta = dict(getattr(messages, "meta", {}))
    response_context_meta["recall_tool_enabled"] = recall_tool_enabled
    observer.note_response_context(response_context_meta)
    cfg = resolve_structured_llm_config(scenario="chat")
    final = {
        "type": "final", "content": "", "reasoning": None,
        "tool_calls": None, "prompt_tokens": None,
        "completion_tokens": None, "duration_ms": None,
    }
    async for event in respond.stream(
        messages,
        stream=stream,
        through_turn=user_turn - 1,
        exclude_recall_turns=set(
            response_context_meta.get("history_turns") or (),
        ),
        recall_summary_mode="digest",
        recall_max_tokens=config.response_recall_tokens(),
        recall_enabled=recall_tool_enabled,
    ):
        if event["type"] == "final":
            final = {**event, "route": decision.route, "run_id": run_id}
        else:
            yield event

    assistant = ingest.persist_assistant(final["content"], stream=stream)
    if applied.close_pending:
        try:
            applied = service.finalize_deferred_close(
                applied,
                user_turn=user_turn,
                run_id=f"{run_id}:delivered",
            )
        except Exception as exc:
            # The user-facing answer is already durable. Keep the Inquiry in
            # reviewing state so a later turn can safely retry closure.
            close_error = f"{type(exc).__name__}: {exc}"[:500]
            controller_error = (
                f"{controller_error}; {close_error}"
                if controller_error else close_error
            )
    observer.persist_controller_spans(assistant["turn"])
    _trace(
        assistant_turn=assistant["turn"], stream=stream, run_id=run_id,
        snapshot=snapshot, applied=applied, model=cfg.get("model"),
        prompt=messages, output=final["content"], final=final,
        controller_error=controller_error,
        context_meta=response_context_meta,
        pipeline_sequence=observer.chat_pipeline_sequence(),
        normalized_fields=observer.controller_normalized_fields,
    )
    observer.complete(
        assistant_turn=assistant["turn"], applied=applied,
        responder_model=cfg.get("model"), controller_error=controller_error,
    )
    schedule_background()
    yield final
