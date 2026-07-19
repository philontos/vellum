import json

from fastapi.testclient import TestClient

from app.data_scope import user_scope
from app.store import traces, turn_runs


def _start_run(
    run_id: str,
    *,
    user_turn: int,
    route: str = "direct",
    status: str = "done",
    stream: str = "neutral",
    context_meta: dict | None = None,
    error: str | None = None,
) -> None:
    turn_runs.start(
        run_id=run_id,
        user_turn=user_turn,
        stream=stream,
        context_meta=context_meta or {},
        prompt_release_id=7,
        prompt_release_version=3,
    )
    if status == "error":
        turn_runs.fail(run_id, error or "pipeline failed")
        return
    turn_runs.finish(
        run_id=run_id,
        assistant_turn=user_turn + 1,
        route=route,
        status=status,
        inquiry_id=None,
        revision_before=None,
        revision_after=None,
        controller_model="controller-model",
        responder_model="responder-model" if route != "inquire" else None,
        decision={"route": route},
        error=error,
    )


def _trace(
    run_id: str,
    *,
    turn: int,
    stage: str,
    model: str,
    duration_ms: int,
    attempt: int = 1,
    params: dict | None = None,
    prompt: object | None = None,
    output: str = "ok",
    tool_calls: list[dict] | None = None,
    pinned: bool = False,
) -> int:
    return traces.record(
        turn=turn,
        stage=stage,
        model=model,
        params=params or {},
        prompt=json.dumps(prompt if prompt is not None else {"input": stage}),
        output=output,
        reasoning="reasoning",
        tool_calls=tool_calls or [
            {"name": "recall_memory", "args": {}, "result": "hit", "ok": True},
        ],
        prompt_tokens=10,
        completion_tokens=4,
        duration_ms=duration_ms,
        pinned=pinned,
        run_id=run_id,
        scenario="inquiry" if stage.startswith("inquiry.") else "chat",
        attempt=attempt,
    )


def test_trace_review_lists_filtered_runs_with_lightweight_span_summary(migrated_db):
    from app.main import app

    _start_run("done-run", user_turn=4)
    _trace(
        "done-run", turn=5, stage="inquiry.decide",
        model="controller-model", duration_ms=30,
        params={"status": "ok"},
    )
    _trace(
        "done-run", turn=5, stage="chat",
        model="responder-model", duration_ms=70,
    )
    _start_run(
        "failed-run", user_turn=8, route="direct", status="error",
        error="responder unavailable",
    )
    _trace(
        "failed-run", turn=8, stage="inquiry.decide",
        model="controller-model", duration_ms=20,
    )

    response = TestClient(app).get(
        "/inspect/trace-review/runs",
        params={
            "status": "done", "route": "direct", "stream": "neutral",
            "user_turn": 4,
        },
    )

    assert response.status_code == 200
    rows = response.json()["runs"]
    assert [row["id"] for row in rows] == ["done-run"]
    assert rows[0]["trace_summary"] == {
        "trace_count": 2,
        "stages": ["inquiry.decide", "chat"],
        "models": ["controller-model", "responder-model"],
        "prompt_tokens": 20,
        "completion_tokens": 8,
        "total_duration_ms": 100,
        "error_count": 0,
        "retry_count": 0,
        "pruned_trace_count": 0,
    }
    serialized = json.dumps(rows)
    assert "reasoning" not in serialized
    assert "recall_memory" not in serialized
    assert "\"input\"" not in serialized

    assert TestClient(app).get(
        "/inspect/trace-review/runs", params={"status": "unknown"},
    ).status_code == 422


def test_trace_review_recency_is_stable_for_runs_started_in_the_same_second(migrated_db):
    from app.main import app

    _start_run("z-first", user_turn=30)
    _start_run("a-second", user_turn=32)

    rows = TestClient(app).get(
        "/inspect/trace-review/runs", params={"limit": 1},
    ).json()["runs"]

    assert [row["id"] for row in rows] == ["a-second"]


def test_trace_review_detail_decodes_bodies_and_surfaces_objective_signals(migrated_db):
    from app.main import app

    _start_run(
        "degraded-run",
        user_turn=10,
        route="direct",
        status="degraded",
        context_meta={
            "estimated_tokens": 950,
            "max_input_tokens": 1_000,
            "dropped_recent_messages": 2,
            "dropped_cited_evidence": 1,
            "current_user_turn_truncated": True,
        },
        error="ControllerValidationError: invalid patch",
    )
    first = _trace(
        "degraded-run",
        turn=11,
        stage="inquiry.decide",
        model="controller-model",
        duration_ms=50,
        params={"status": "ok", "context": {"scenario": "inquiry"}},
        prompt={"system_prompt": "control", "user_prompt": "input"},
        output='{"route":"direct"}',
    )
    second = _trace(
        "degraded-run",
        turn=11,
        stage="chat",
        model="responder-model",
        duration_ms=120,
        attempt=2,
        params={"status": "error", "error": "first provider attempt failed"},
        prompt=[{"role": "user", "content": "Help"}],
        output="Answer",
    )

    response = TestClient(app).get(
        "/inspect/trace-review/runs/degraded-run",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["id"] == "degraded-run"
    assert [span["id"] for span in payload["traces"]] == [first, second]
    assert payload["traces"][0]["params"]["context"] == {"scenario": "inquiry"}
    assert payload["traces"][0]["prompt"]["system_prompt"] == "control"
    assert payload["traces"][1]["prompt"][0]["content"] == "Help"
    assert payload["traces"][1]["tool_calls"][0]["name"] == "recall_memory"
    assert payload["traces"][1]["output"] == "Answer"
    assert payload["trace_summary"]["total_duration_ms"] == 170

    signal_codes = {signal["code"] for signal in payload["signals"]}
    assert signal_codes == {
        "run.degraded",
        "context.near_limit",
        "context.items_dropped",
        "context.current_turn_truncated",
        "trace.call_error",
        "trace.retry",
    }

    assert TestClient(app).get(
        "/inspect/trace-review/runs/missing-run",
    ).status_code == 404


def test_trace_review_stats_aggregate_recent_runs_by_stage_and_model(migrated_db):
    from app.main import app

    _start_run("run-a", user_turn=2, route="direct", status="done")
    _trace(
        "run-a", turn=3, stage="inquiry.decide",
        model="controller-model", duration_ms=20,
        params={"status": "ok"},
    )
    _trace(
        "run-a", turn=3, stage="chat",
        model="responder-model", duration_ms=100,
    )
    _start_run(
        "run-b", user_turn=4, route="direct", status="error",
        error="timeout",
    )
    _trace(
        "run-b", turn=4, stage="inquiry.decide",
        model="controller-model", duration_ms=300, attempt=2,
        params={"status": "error", "error": "timeout"},
    )

    client = TestClient(app)
    payload = client.get("/inspect/trace-review/stats", params={"limit": 10}).json()

    assert payload["window"]["run_count"] == 2
    assert payload["window"]["trace_count"] == 3
    assert payload["runs"]["by_status"] == {"done": 1, "error": 1}
    assert payload["runs"]["by_route"] == {"direct": 1, "unknown": 1}
    assert payload["totals"] == {
        "prompt_tokens": 30,
        "completion_tokens": 12,
        "duration_ms": 420,
        "trace_errors": 1,
        "retries": 1,
    }

    by_stage = {row["key"]: row for row in payload["by_stage"]}
    assert by_stage["inquiry.decide"]["calls"] == 2
    assert by_stage["inquiry.decide"]["errors"] == 1
    assert by_stage["inquiry.decide"]["duration_ms"]["p95"] == 300
    assert by_stage["chat"]["duration_ms"]["p50"] == 100

    by_model = {row["key"]: row for row in payload["by_model"]}
    assert by_model["controller-model"]["calls"] == 2
    assert by_model["responder-model"]["calls"] == 1

    done_only = client.get(
        "/inspect/trace-review/stats", params={"status": "done"},
    ).json()
    assert done_only["window"]["run_count"] == 1
    assert done_only["window"]["trace_count"] == 2


def test_trace_review_flags_failed_tools_and_incomplete_diagnostic_bodies(migrated_db):
    from app.main import app

    _start_run("tool-run", user_turn=20)
    trace_id = _trace(
        "tool-run",
        turn=21,
        stage="chat",
        model="responder-model",
        duration_ms=80,
        tool_calls=[{
            "name": "web_search",
            "args": {"query": "latest"},
            "result": "ERROR provider unavailable",
            "ok": False,
        }],
        pinned=True,
    )
    pruned_id = _trace(
        "tool-run",
        turn=21,
        stage="inquiry.decide",
        model="controller-model",
        duration_ms=20,
    )
    traces.prune(keep_last=0)

    payload = TestClient(app).get(
        "/inspect/trace-review/runs/tool-run",
    ).json()

    signals = {signal["code"]: signal for signal in payload["signals"]}
    assert signals["tool.call_error"]["evidence"] == {
        "calls": [{"trace_id": trace_id, "name": "web_search"}],
    }
    assert signals["trace.body_pruned"]["evidence"] == {
        "trace_ids": [pruned_id],
    }
    assert payload["trace_summary"]["pruned_trace_count"] == 1


def test_trace_review_routes_follow_authenticated_account_scope(tmp_path, monkeypatch):
    from app.auth import accounts
    from app.main import create_app

    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    alice = accounts.create_user(
        "alice", "Alice", "correct horse battery staple", role="owner",
    )
    bob = accounts.create_user(
        "bob", "Bob", "another correct horse battery staple",
    )
    with user_scope(alice["id"]):
        _start_run("alice-run", user_turn=2)
        _trace(
            "alice-run", turn=3, stage="chat",
            model="alice-model", duration_ms=10,
        )
    with user_scope(bob["id"]):
        _start_run("bob-run", user_turn=6)
        _trace(
            "bob-run", turn=7, stage="chat",
            model="bob-model", duration_ms=10,
        )

    client = TestClient(create_app())
    assert client.get("/inspect/trace-review/runs").status_code == 401
    assert client.post(
        "/auth/login",
        json={
            "username": "alice",
            "password": "correct horse battery staple",
        },
    ).status_code == 200

    rows = client.get("/inspect/trace-review/runs").json()["runs"]
    assert [row["id"] for row in rows] == ["alice-run"]
    assert client.get(
        "/inspect/trace-review/runs/bob-run",
    ).status_code == 404


def test_trace_review_endpoints_are_described_in_openapi(migrated_db):
    from app.main import app

    paths = TestClient(app).get("/openapi.json").json()["paths"]

    for path in (
        "/inspect/trace-review/runs",
        "/inspect/trace-review/runs/{run_id}",
        "/inspect/trace-review/stats",
    ):
        operation = paths[path]["get"]
        assert operation["summary"]
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema
