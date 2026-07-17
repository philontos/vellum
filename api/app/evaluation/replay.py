"""Build the frozen model input for one historical conversation replay."""
import json
import re
from dataclasses import dataclass

from app import config
from app.chat import assemble, temporal
from app.prompts import runtime, service as prompt_service
from app.prompts.catalog import definitions
from app.store import memory, observability as obs, traces


class ConversationRoundNotFoundError(KeyError):
    pass


class ReplayValidationError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedReplay:
    round: dict
    messages: list[dict]
    snapshot: runtime.PromptSnapshot
    prompt_kind: str
    prompt_label: str
    prompt_release_id: int | None = None
    prompt_release_version: int | None = None
    prompt_version_id: int | None = None

    @property
    def system_prompt(self) -> str:
        first = self.messages[0] if self.messages else {}
        return first.get("content", "") if first.get("role") == "system" else ""


def trace_params(trace: dict | None) -> dict:
    if not trace or not trace.get("params"):
        return {}
    try:
        value = json.loads(trace["params"])
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def trace_messages(trace: dict | None) -> list[dict] | None:
    if not trace or not trace.get("prompt"):
        return None
    try:
        value = json.loads(trace["prompt"])
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, list):
        return None
    messages = [
        {"role": item.get("role"), "content": item.get("content", ""),
         **({"name": item["name"]} if "name" in item else {})}
        for item in value
        if isinstance(item, dict) and isinstance(item.get("role"), str)
    ]
    if not messages or messages[0].get("role") != "system":
        return None
    return messages


def system_prompt(messages: list[dict] | None) -> str | None:
    if not messages or messages[0].get("role") != "system":
        return None
    content = messages[0].get("content")
    return content if isinstance(content, str) else None


def source_snapshot(trace: dict | None) -> runtime.PromptSnapshot:
    release_id = trace_params(trace).get("prompt_release_id")
    if isinstance(release_id, int):
        try:
            return runtime.snapshot_for_release(release_id)
        except prompt_service.UnknownReleaseError:
            # A trace can outlive a restored Prompt database. Its rendered system
            # input remains usable; code defaults are the safest tool fallback.
            pass
    return runtime.default_snapshot()


def trace_view(trace: dict | None) -> dict:
    if trace is None:
        return {
            "trace_id": None,
            "prompt_release_id": None,
            "prompt_release_version": None,
            "model": None,
            "replayable": False,
        }
    params = trace_params(trace)
    return {
        "trace_id": trace["id"],
        "prompt_release_id": params.get("prompt_release_id"),
        "prompt_release_version": params.get("prompt_release_version"),
        "model": trace.get("model"),
        "replayable": trace_messages(trace) is not None,
    }


def _rendered_fragment(content: str, template_format: str, system: str) -> str | None:
    if template_format == "literal":
        return content
    if template_format == "format" and "{current_time}" in content:
        match = re.search(r"<current_time\b[^>]*/>", system)
        if match:
            try:
                return content.format(current_time=match.group(0))
            except (KeyError, ValueError):
                return None
    return None


def _apply_release(
    messages: list[dict], source: runtime.PromptSnapshot,
    target: runtime.PromptSnapshot,
) -> list[dict]:
    """Swap release-owned chat fragments while freezing contextual evidence."""
    copied = [dict(message) for message in messages]
    system = copied[0]["content"]
    for definition in definitions():
        if definition.category != "chat":
            continue
        source_content = source.contents.get(definition.key, definition.default_content)
        target_content = target.contents.get(definition.key, definition.default_content)
        if source_content == target_content:
            continue
        rendered_source = _rendered_fragment(
            source_content, definition.template_format, system,
        )
        rendered_target = _rendered_fragment(
            target_content, definition.template_format, system,
        )
        if rendered_source and rendered_target and rendered_source in system:
            system = system.replace(rendered_source, rendered_target, 1)
    copied[0] = {**copied[0], "content": system}
    return copied


async def _historical_messages(
    row: dict, snapshot: runtime.PromptSnapshot,
) -> list[dict]:
    with runtime.use_snapshot(snapshot):
        return await assemble.build_messages(
            query=row["user_content"],
            persona_name=row["stream"],
            through_turn=row["user_turn"],
        )


async def prepare_replay(
    assistant_turn: int, prompt_kind: str, *,
    prompt_release_id: int | None = None,
    prompt_version_id: int | None = None,
) -> PreparedReplay:
    row = memory.get_conversation_round(assistant_turn)
    if row is None:
        raise ConversationRoundNotFoundError(assistant_turn)
    trace = traces.chat_for_turn(assistant_turn)
    source_messages = trace_messages(trace)
    original_snapshot = source_snapshot(trace)
    params = trace_params(trace)

    if prompt_kind == "original":
        if source_messages is None:
            raise ReplayValidationError(
                "This round has no original Prompt snapshot; choose a published "
                "or saved Prompt version instead"
            )
        version = params.get("prompt_release_version")
        label = f"Original · v{version}" if version is not None else "Original Prompt"
        return PreparedReplay(
            round=row, messages=source_messages, snapshot=original_snapshot,
            prompt_kind="original", prompt_label=label,
            prompt_release_id=params.get("prompt_release_id"),
            prompt_release_version=version,
        )

    if prompt_kind == "release":
        if prompt_release_id is None:
            raise ReplayValidationError("A published Prompt release is required")
        try:
            target = runtime.snapshot_for_release(prompt_release_id)
        except prompt_service.UnknownReleaseError as exc:
            raise ReplayValidationError(
                f"Unknown Prompt release: {prompt_release_id}"
            ) from exc
        messages = (
            _apply_release(source_messages, original_snapshot, target)
            if source_messages is not None
            else await _historical_messages(row, target)
        )
        return PreparedReplay(
            round=row, messages=messages, snapshot=target,
            prompt_kind="release", prompt_label=f"Release v{target.release_version}",
            prompt_release_id=target.release_id,
            prompt_release_version=target.release_version,
        )

    if prompt_kind == "custom":
        if prompt_version_id is None:
            raise ReplayValidationError("A saved Prompt version is required")
        version = obs.get_conversation_prompt_version(prompt_version_id)
        if version is None:
            raise ReplayValidationError(
                f"Unknown Prompt version: {prompt_version_id}"
            )
        base = source_messages
        if base is None:
            rows = memory.recent_tail_through(
                config.tail_size(), row["user_turn"], stream=row["stream"],
            )
            base = [
                {"role": "system", "content": version["content"]},
                *temporal.annotate_messages(rows),
            ]
        else:
            base = [dict(message) for message in base]
            base[0] = {**base[0], "content": version["content"]}
        return PreparedReplay(
            round=row, messages=base, snapshot=original_snapshot,
            prompt_kind="custom", prompt_label=version["name"],
            prompt_version_id=version["id"],
        )

    raise ReplayValidationError(f"Unknown Prompt kind: {prompt_kind}")
