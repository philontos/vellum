"""Immutable conversation-evaluation archives, independent of their source turn."""
import json
from types import MappingProxyType

from app.evaluation.replay import (
    PreparedReplay,
    prepare_replay,
    trace_messages,
    trace_params,
)
from app.prompts import runtime, service as prompt_service
from app.store import conversation_evals as eval_store, traces


class ConversationEvalRecordNotFoundError(KeyError):
    pass


def _original_label(params: dict) -> str:
    version = params.get("prompt_release_version")
    return f"Original · v{version}" if version is not None else "Original Prompt"


async def create_record(
    assistant_turn: int,
    prompt_kind: str,
    *,
    prompt_release_id: int | None = None,
    prompt_version_id: int | None = None,
) -> dict:
    """Fork one source round and freeze every input needed for future reruns."""
    prepared = await prepare_replay(
        assistant_turn,
        prompt_kind,
        prompt_release_id=prompt_release_id,
        prompt_version_id=prompt_version_id,
    )
    trace = traces.chat_for_turn(assistant_turn)
    baseline_messages = trace_messages(trace)
    baseline_params = trace_params(trace)
    record = eval_store.create_record({
        "source_user_turn": prepared.round["user_turn"],
        "source_assistant_turn": prepared.round["assistant_turn"],
        "stream": prepared.round["stream"],
        "source_created_at": prepared.round.get("created_at"),
        "source_user_content": prepared.round["user_content"],
        "baseline_output": prepared.round["original_content"],
        "baseline_prompt_release_id": baseline_params.get("prompt_release_id"),
        "baseline_prompt_release_version": baseline_params.get(
            "prompt_release_version"
        ),
        "baseline_prompt_label": _original_label(baseline_params),
        "baseline_system_prompt": (
            baseline_messages[0]["content"] if baseline_messages else None
        ),
        "baseline_input_json": (
            json.dumps(baseline_messages, ensure_ascii=False)
            if baseline_messages is not None else None
        ),
        "prompt_kind": prepared.prompt_kind,
        "prompt_release_id": prepared.prompt_release_id,
        "prompt_release_version": prepared.prompt_release_version,
        "prompt_version_id": prepared.prompt_version_id,
        "prompt_label": prepared.prompt_label,
        "system_prompt": prepared.system_prompt,
        "input_json": json.dumps(prepared.messages, ensure_ascii=False),
        "runtime_snapshot_json": json.dumps(
            dict(prepared.snapshot.contents), ensure_ascii=False,
        ),
    })
    return _detail(record)


def list_records(limit: int = 50, before: int | None = None) -> dict:
    rows = eval_store.list_records(limit + 1, before=before)
    return {"records": rows[:limit], "has_more": len(rows) > limit}


def _detail(record: dict) -> dict:
    view = dict(record)
    view.pop("runtime_snapshot", None)
    runs = eval_store.runs_for_record(record["id"])
    view["runs"] = runs
    view["run_count"] = len(runs)
    view["latest_status"] = runs[0]["status"] if runs else None
    view["latest_output"] = runs[0]["output"] if runs else None
    return view


def record_detail(record_id: int) -> dict:
    record = eval_store.get_record(record_id)
    if record is None:
        raise ConversationEvalRecordNotFoundError(record_id)
    return _detail(record)


def _fallback_snapshot(record: dict) -> runtime.PromptSnapshot:
    release_id = (
        record.get("prompt_release_id")
        if record.get("prompt_kind") == "release"
        else record.get("baseline_prompt_release_id")
    )
    if isinstance(release_id, int):
        try:
            return runtime.snapshot_for_release(release_id)
        except prompt_service.UnknownReleaseError:
            pass
    return runtime.default_snapshot()


def prepared_for_record(record_id: int) -> PreparedReplay:
    """Rehydrate an archived input without reading mutable conversation history."""
    record = eval_store.get_record(record_id)
    if record is None:
        raise ConversationEvalRecordNotFoundError(record_id)
    contents = record.get("runtime_snapshot")
    if contents:
        fallback = _fallback_snapshot(record)
        snapshot = runtime.PromptSnapshot(
            release_id=fallback.release_id,
            release_version=fallback.release_version,
            contents=MappingProxyType(dict(contents)),
        )
    else:
        snapshot = _fallback_snapshot(record)
    messages = record.get("input")
    if not isinstance(messages, list):
        raise ValueError(f"Evaluation record {record_id} has no valid input snapshot")
    return PreparedReplay(
        round={
            "user_turn": record["source_user_turn"],
            "assistant_turn": record["source_assistant_turn"],
            "stream": record["stream"],
            "created_at": record.get("source_created_at"),
            "user_content": record["source_user_content"],
            "original_content": record["baseline_output"],
        },
        messages=messages,
        snapshot=snapshot,
        prompt_kind=record["prompt_kind"],
        prompt_label=record["prompt_label"],
        prompt_release_id=record.get("prompt_release_id"),
        prompt_release_version=record.get("prompt_release_version"),
        prompt_version_id=record.get("prompt_version_id"),
    )
