import json

import pytest

from app.chat import assemble, converse, orchestrator, persona, respond
from app.data_scope import user_scope
from app.llm.client import _record_llm_call
from app.model_loop import runner, summary
from app.prompts import runtime, service
from app.store import db, memory, traces


def _publish_changed(key: str, marker: str) -> None:
    workspace = service.get_workspace()
    item = next(prompt for prompt in workspace["prompts"] if prompt["key"] == key)
    content = marker + "\n" + item["draft_content"]
    workspace = service.save_draft(key, content, workspace["workspace_revision"])
    service.publish(workspace["workspace_revision"], "runtime test")


def _save_changed_drafts(changes: dict[str, str]) -> dict:
    """Save several prompt changes without publishing the resulting workspace."""
    workspace = service.get_workspace()
    for key, marker in changes.items():
        item = next(prompt for prompt in workspace["prompts"] if prompt["key"] == key)
        workspace = service.save_draft(
            key,
            marker + "\n" + item["draft_content"],
            workspace["workspace_revision"],
        )
    return workspace


def _publish_changes(changes: dict[str, str], note: str) -> None:
    workspace = _save_changed_drafts(changes)
    service.publish(workspace["workspace_revision"], note)


@pytest.mark.asyncio
async def test_summary_job_uses_the_active_release(migrated_db, monkeypatch):
    seen = {}

    async def fake_chat_json(system_prompt, user_prompt="", **kwargs):
        seen["prompt"] = system_prompt
        return {"summary": "digest"}

    async def fake_embed(text):
        return [1.0, 0.0]

    monkeypatch.setattr(summary, "chat_json", fake_chat_json)
    monkeypatch.setattr(summary, "embed", fake_embed)
    _publish_changed("memory.summary", "RELEASED SUMMARY MARKER")
    memory.append_message("user", "remember this")

    await summary.run(0, 0)

    assert "RELEASED SUMMARY MARKER" in seen["prompt"]


@pytest.mark.asyncio
async def test_chat_assembly_uses_one_active_release(migrated_db, monkeypatch):
    async def fake_retrieve(query, **kwargs):
        return []

    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    _publish_changed("chat.response_protocol", "RELEASED CHAT MARKER")
    memory.append_message("user", "hello")

    messages = await assemble.build_messages()

    assert "RELEASED CHAT MARKER" in messages[0]["content"]


@pytest.mark.asyncio
async def test_chat_assembly_pins_one_release_when_publish_happens_mid_build(
    migrated_db, monkeypatch,
):
    """Voice and shared fragments must never come from different releases."""
    async def fake_retrieve(query, **kwargs):
        return []

    monkeypatch.setattr(assemble.retrieval, "retrieve", fake_retrieve)
    _publish_changes(
        {
            "chat.neutral.voice": "VOICE FROM RELEASE A",
            "chat.response_protocol": "RULES FROM RELEASE A",
        },
        "release A",
    )
    pending = _save_changed_drafts(
        {
            "chat.neutral.voice": "VOICE FROM RELEASE B",
            "chat.response_protocol": "RULES FROM RELEASE B",
        }
    )

    original_load = persona.load
    published = False

    def publish_after_voice(name=None):
        nonlocal published
        loaded = original_load(name)
        if not published:
            published = True
            service.publish(pending["workspace_revision"], "release B")
        return loaded

    monkeypatch.setattr(assemble.persona, "load", publish_after_voice)
    memory.append_message("user", "hello")

    system = (await assemble.build_messages())[0]["content"]

    assert "VOICE FROM RELEASE A" in system
    assert "RULES FROM RELEASE A" in system
    assert "VOICE FROM RELEASE B" not in system
    assert "RULES FROM RELEASE B" not in system


@pytest.mark.asyncio
async def test_chat_trace_keeps_the_release_that_started_the_turn(migrated_db, monkeypatch):
    _publish_changed("chat.response_protocol", "CHAT RELEASE A")
    started = runtime.active_snapshot()
    pending = _save_changed_drafts({"chat.response_protocol": "CHAT RELEASE B"})

    async def fake_embed(text):
        return [1.0, 0.0]

    async def fake_retrieve(query, **kwargs):
        return []

    async def publish_while_streaming(messages, stream="neutral"):
        service.publish(pending["workspace_revision"], "publish during chat")
        yield {
            "type": "final",
            "content": "answer",
            "reasoning": None,
            "tool_calls": None,
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "duration_ms": 1,
        }

    async def no_background_work():
        return None

    monkeypatch.setattr(orchestrator.ingest, "embed", fake_embed)
    monkeypatch.setattr(orchestrator.assemble.retrieval, "retrieve", fake_retrieve)
    monkeypatch.setattr(respond, "stream", publish_while_streaming)
    monkeypatch.setattr(runner, "run_pending", no_background_work)

    assert await converse.reply("hello") == "answer"

    row = next(row for row in traces.list_recent(10) if row["stage"] == "chat")
    params = json.loads(row["params"])
    assert params["prompt_release_id"] == started.release_id
    assert params["prompt_release_version"] == started.release_version
    assert runtime.active_snapshot().release_id != started.release_id


@pytest.mark.asyncio
async def test_runner_pins_one_release_and_records_it_on_every_batch_trace(
    migrated_db, monkeypatch,
):
    _publish_changed("memory.summary", "RUNNER RELEASE A")
    started = runtime.active_snapshot()
    pending = _save_changed_drafts({"memory.summary": "RUNNER RELEASE B"})
    memory.append_message("user", "one turn is enough")

    monkeypatch.setattr(runner.config, "trait_batch_k", lambda: 1)
    monkeypatch.setattr(runner.config, "dossier_batch_m", lambda: 1)
    monkeypatch.setattr(runner.config, "summary_span_s", lambda: 1)
    seen: list[tuple[str, str]] = []

    def record(stage: str) -> None:
        content = runtime.resolve("memory.summary", "fallback")
        seen.append((stage, content))
        _record_llm_call({
            "stage": stage,
            "model": "m",
            "status": "ok",
            "system_prompt": content,
            "user_prompt": "",
            "response": "{}",
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "duration_ms": 1,
        })

    async def facts_job(start, end):
        record("facts")
        service.publish(pending["workspace_revision"], "publish during runner")

    async def trait_job(start, end, dimension):
        record("trait")

    async def dossier_job(start, end):
        record("dossier")

    async def summary_job(start, end, stream="neutral"):
        record("summary")

    monkeypatch.setattr(runner.facts, "run", facts_job)
    monkeypatch.setattr(runner.traits, "run_dimension", trait_job)
    monkeypatch.setattr(runner, "DIMENSION_MAP", {"ocean": {}})
    monkeypatch.setattr(runner.dossier, "run", dossier_job)
    monkeypatch.setattr(runner.summary, "run", summary_job)

    await runner.run_pending()

    assert [stage for stage, _content in seen] == [
        "facts", "trait", "dossier", "summary",
    ]
    assert all("RUNNER RELEASE A" in content for _stage, content in seen)
    assert all("RUNNER RELEASE B" not in content for _stage, content in seen)
    assert runtime.active_snapshot().release_id != started.release_id

    rows = [row for row in traces.list_recent(20) if row["stage"] in {
        "facts", "trait", "dossier", "summary",
    }]
    assert {row["stage"] for row in rows} == {"facts", "trait", "dossier", "summary"}
    for row in rows:
        params = json.loads(row["params"])
        assert params["prompt_release_id"] == started.release_id
        assert params["prompt_release_version"] == started.release_version


def test_prompt_releases_are_shared_by_every_account(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")

    with user_scope("alice"):
        db.run_migrations()
        _publish_changed("chat.response_protocol", "ALICE ONLY")

    with user_scope("bob"):
        db.run_migrations()
        assert "ALICE ONLY" in next(
            item for item in service.get_workspace()["prompts"]
            if item["key"] == "chat.response_protocol"
        )["published_content"]

    with user_scope("alice"):
        assert "ALICE ONLY" in next(
            item for item in service.get_workspace()["prompts"]
            if item["key"] == "chat.response_protocol"
        )["published_content"]
