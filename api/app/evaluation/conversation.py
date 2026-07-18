"""Catalog, persist, and execute single-turn conversation replay evaluations."""
import asyncio
import json

from app.chat import respond
from app.llm.client import resolve_structured_llm_config
from app.prompts import runtime, service as prompt_service
from app.store import conversation_evals as eval_store, memory, traces

from app.evaluation.replay import (
    ConversationRoundNotFoundError,
    PreparedReplay,
    ReplayValidationError,
    prepare_replay,
    system_prompt,
    trace_messages,
    trace_view,
)


MAX_PROMPT_NAME_CHARS = 80
MAX_PROMPT_CONTENT_CHARS = 200_000


def workspace(limit: int = 50, before: int | None = None) -> dict:
    rows = memory.conversation_rounds(limit + 1, before=before)
    visible = rows[:limit]
    metadata = traces.chat_metadata_by_turn(
        [row["assistant_turn"] for row in visible]
    )
    rounds = []
    for row in visible:
        meta = metadata.get(row["assistant_turn"])
        rounds.append({
            **row,
            "trace_id": meta.get("id") if meta else None,
            "prompt_release_id": meta.get("prompt_release_id") if meta else None,
            "prompt_release_version": (
                meta.get("prompt_release_version") if meta else None
            ),
            "model": meta.get("model") if meta else None,
            "replayable": bool(meta and meta.get("replayable")),
        })
    return {
        "rounds": rounds,
        "releases": prompt_service.list_releases(),
        "prompt_versions": eval_store.list_prompt_versions(),
        "has_more": len(rows) > limit,
    }


def round_detail(assistant_turn: int) -> dict:
    row = memory.get_conversation_round(assistant_turn)
    if row is None:
        raise ConversationRoundNotFoundError(assistant_turn)
    trace = traces.chat_for_turn(assistant_turn)
    messages = trace_messages(trace)
    return {
        "round": {**row, **trace_view(trace)},
        "original_system_prompt": system_prompt(messages),
    }


def create_prompt_version(name: str, content: str) -> dict:
    name = name.strip()
    content = content.strip()
    if not name:
        raise ReplayValidationError("Prompt version name is required")
    if len(name) > MAX_PROMPT_NAME_CHARS:
        raise ReplayValidationError(
            f"Prompt version name must be at most {MAX_PROMPT_NAME_CHARS} characters"
        )
    if not content:
        raise ReplayValidationError("Prompt content is required")
    if len(content) > MAX_PROMPT_CONTENT_CHARS:
        raise ReplayValidationError(
            f"Prompt content must be at most {MAX_PROMPT_CONTENT_CHARS} characters"
        )
    return eval_store.create_prompt_version(name, content)


def start_run(prepared: PreparedReplay, *, record_id: int | None = None) -> dict:
    model_name = resolve_structured_llm_config().get("model") or None
    run_id = eval_store.create_run({
        "record_id": record_id,
        "source_user_turn": prepared.round["user_turn"],
        "source_assistant_turn": prepared.round["assistant_turn"],
        "stream": prepared.round["stream"],
        "source_user_content": prepared.round["user_content"],
        "original_content": prepared.round["original_content"],
        "prompt_kind": prepared.prompt_kind,
        "prompt_release_id": prepared.prompt_release_id,
        "prompt_release_version": prepared.prompt_release_version,
        "prompt_version_id": prepared.prompt_version_id,
        "prompt_label": prepared.prompt_label,
        "system_prompt": prepared.system_prompt,
        "input_json": json.dumps(prepared.messages, ensure_ascii=False),
        "model": model_name,
    })
    return eval_store.get_run(run_id)


async def run_events(run_id: int, prepared: PreparedReplay):
    final: dict | None = None
    try:
        with runtime.use_snapshot(prepared.snapshot):
            async for event in respond.stream(
                prepared.messages,
                stream=prepared.round["stream"],
                through_turn=prepared.round["user_turn"],
            ):
                kind = event.get("type")
                if kind == "delta":
                    yield {"type": "delta", "text": event.get("text", "")}
                elif kind in {"tool_start", "tool_end"}:
                    yield {"type": "activity", "activity": event}
                elif kind == "final":
                    final = event
        final = final or {"content": ""}
        eval_store.finish_run(
            run_id,
            output=final.get("content", ""),
            reasoning=final.get("reasoning"),
            tool_calls=final.get("tool_calls"),
            prompt_tokens=final.get("prompt_tokens"),
            completion_tokens=final.get("completion_tokens"),
            duration_ms=final.get("duration_ms"),
        )
        yield {"type": "done", "run": eval_store.get_run(run_id)}
    except asyncio.CancelledError:
        eval_store.fail_run(run_id, "Replay cancelled")
        raise
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        eval_store.fail_run(run_id, message)
        yield {"type": "done", "run": eval_store.get_run(run_id)}
