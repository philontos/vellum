"""Standalone conversation-eval archives and their immutable Prompt snapshots."""
import json

from fastapi.testclient import TestClient


def _conversation_with_trace(user: str = "Which path should I take?") -> int:
    from app.store import memory, traces

    memory.append_message("user", user)
    answer = memory.append_message("assistant", "Baseline answer")
    traces.record(
        turn=answer["turn"],
        stage="chat",
        model="baseline-model",
        params={
            "persona": "neutral",
            "prompt_release_id": 7,
            "prompt_release_version": 3,
        },
        prompt=json.dumps([
            {"role": "system", "content": "BASELINE SYSTEM"},
            {"role": "user", "content": user},
        ]),
        output="Baseline answer",
        prompt_tokens=11,
        completion_tokens=13,
        duration_ms=17,
    )
    return answer["turn"]


def _prompt_version(client: TestClient, name: str, content: str) -> dict:
    response = client.post(
        "/inspect/conversation-evals/prompt-versions",
        json={"name": name, "content": content},
    )
    assert response.status_code == 201
    return response.json()


def _record(client: TestClient, turn: int, version: dict) -> dict:
    response = client.post(
        "/inspect/conversation-evals/records",
        json={
            "assistant_turn": turn,
            "prompt_kind": "custom",
            "prompt_version_id": version["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_record_is_a_standalone_archive_with_full_prompt_snapshots(migrated_db):
    from app.main import app

    turn = _conversation_with_trace()
    client = TestClient(app)
    version = _prompt_version(client, "Sharper experiment", "EVALUATED SYSTEM")

    record = _record(client, turn, version)

    assert record["id"] > 0
    assert record["source_assistant_turn"] == turn
    assert record["source_user_content"] == "Which path should I take?"
    assert record["baseline_output"] == "Baseline answer"
    assert record["baseline_prompt_label"] == "Original · v3"
    assert record["baseline_system_prompt"] == "BASELINE SYSTEM"
    assert record["prompt_label"] == "Sharper experiment"
    assert record["prompt_kind"] == "custom"
    assert record["system_prompt"] == "EVALUATED SYSTEM"
    assert record["baseline_input"][0]["content"] == "BASELINE SYSTEM"
    assert record["input"][0]["content"] == "EVALUATED SYSTEM"
    assert record["runs"] == []

    archive = client.get("/inspect/conversation-evals/records?limit=20")
    assert archive.status_code == 200
    assert archive.json()["records"][0] == {
        "id": record["id"],
        "source_user_turn": turn - 1,
        "source_assistant_turn": turn,
        "stream": "neutral",
        "source_user_content": "Which path should I take?",
        "baseline_output": "Baseline answer",
        "baseline_prompt_label": "Original · v3",
        "prompt_kind": "custom",
        "prompt_release_id": None,
        "prompt_release_version": None,
        "prompt_version_id": version["id"],
        "prompt_label": "Sharper experiment",
        "run_count": 0,
        "latest_status": None,
        "latest_output": None,
        "created_at": record["created_at"],
    }
    assert archive.json()["has_more"] is False

    source = client.get(f"/inspect/conversation-evals/rounds/{turn}").json()
    assert "runs" not in source


def test_runs_belong_to_one_record_not_to_the_source_round(migrated_db, monkeypatch):
    from app.evaluation import conversation
    from app.main import app

    turn = _conversation_with_trace("Fork this input")
    client = TestClient(app)
    first = _record(client, turn, _prompt_version(client, "First", "PROMPT A"))
    second = _record(client, turn, _prompt_version(client, "Second", "PROMPT B"))
    outputs = iter(("A1", "A2", "B1"))

    async def fake_stream(messages, stream="neutral", through_turn=None):
        output = next(outputs)
        yield {
            "type": "final",
            "content": output,
            "reasoning": None,
            "tool_calls": None,
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "duration_ms": 5,
        }

    monkeypatch.setattr(conversation.respond, "stream", fake_stream)
    for record_id in (first["id"], first["id"], second["id"]):
        with client.stream(
            "POST", f"/inspect/conversation-evals/records/{record_id}/runs",
        ) as response:
            assert response.status_code == 200
            assert "[DONE]" in "".join(response.iter_text())

    first_detail = client.get(
        f"/inspect/conversation-evals/records/{first['id']}"
    ).json()
    second_detail = client.get(
        f"/inspect/conversation-evals/records/{second['id']}"
    ).json()
    assert [run["output"] for run in first_detail["runs"]] == ["A2", "A1"]
    assert [run["record_id"] for run in first_detail["runs"]] == [
        first["id"], first["id"],
    ]
    assert [run["output"] for run in second_detail["runs"]] == ["B1"]
    assert second_detail["system_prompt"] == "PROMPT B"

    source = client.get(f"/inspect/conversation-evals/rounds/{turn}").json()
    assert "runs" not in source


def test_existing_unarchived_runs_are_backfilled_once(migrated_db):
    from app import config
    from app.store import conversation_evals as eval_store, observability

    turn = _conversation_with_trace("Legacy input")
    run_id = eval_store.create_run({
        "record_id": None,
        "source_user_turn": turn - 1,
        "source_assistant_turn": turn,
        "stream": "neutral",
        "source_user_content": "Legacy input",
        "original_content": "Baseline answer",
        "prompt_kind": "custom",
        "prompt_release_id": None,
        "prompt_release_version": None,
        "prompt_version_id": None,
        "prompt_label": "Legacy experiment",
        "system_prompt": "LEGACY SYSTEM",
        "input_json": json.dumps([
            {"role": "system", "content": "LEGACY SYSTEM"},
            {"role": "user", "content": "Legacy input"},
        ]),
        "model": "legacy-model",
    })
    eval_store.finish_run(
        run_id,
        output="Legacy output",
        reasoning=None,
        tool_calls=None,
        prompt_tokens=2,
        completion_tokens=3,
        duration_ms=4,
    )
    assert eval_store.list_records() == []

    observability.discard_path(config.observability_db_path())

    records = eval_store.list_records()
    assert len(records) == 1
    detail = eval_store.get_record(records[0]["id"])
    assert detail["baseline_system_prompt"] == "BASELINE SYSTEM"
    assert detail["system_prompt"] == "LEGACY SYSTEM"
    assert eval_store.get_run(run_id)["record_id"] == detail["id"]

    observability.discard_path(config.observability_db_path())
    assert len(eval_store.list_records()) == 1


def test_archive_survives_source_history_deletion(migrated_db, monkeypatch):
    from app.evaluation import conversation
    from app.main import app
    from app.store import memory

    turn = _conversation_with_trace("Archive me")
    client = TestClient(app)
    record = _record(
        client, turn, _prompt_version(client, "Durable", "ARCHIVED SYSTEM"),
    )
    assert memory.soft_delete(turn - 1) is True
    assert memory.soft_delete(turn) is True
    assert client.get(f"/inspect/conversation-evals/rounds/{turn}").status_code == 404

    async def fake_stream(messages, stream="neutral", through_turn=None):
        assert messages[0]["content"] == "ARCHIVED SYSTEM"
        yield {
            "type": "final",
            "content": "Still reproducible",
            "reasoning": None,
            "tool_calls": None,
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "duration_ms": 5,
        }

    monkeypatch.setattr(conversation.respond, "stream", fake_stream)
    with client.stream(
        "POST", f"/inspect/conversation-evals/records/{record['id']}/runs",
    ) as response:
        assert response.status_code == 200
        list(response.iter_text())

    detail = client.get(
        f"/inspect/conversation-evals/records/{record['id']}"
    ).json()
    assert detail["source_user_content"] == "Archive me"
    assert detail["baseline_output"] == "Baseline answer"
    assert detail["runs"][0]["output"] == "Still reproducible"
