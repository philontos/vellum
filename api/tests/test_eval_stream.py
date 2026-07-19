"""evals.stream JSONL entrypoint + suites registry: happy path, graceful error
when the model is unconfigured, and recall through in-memory scratch (isolation)."""
import pytest

from app.prompts import runtime, service
from evals import stream, suites


def _capture(monkeypatch):
    frames = []
    monkeypatch.setattr(stream, "_emit", lambda o: frames.append(o))
    return frames


def _record_ok(system_prompt, **kw):
    from app.llm.client import _record_llm_call
    _record_llm_call({"stage": "trait", "model": "m", "status": "ok",
                      "system_prompt": system_prompt, "user_prompt": "",
                      "response": "{...}", "prompt_tokens": 3,
                      "completion_tokens": 4, "duration_ms": 5})


def test_registry_has_all_suites():
    assert set(suites.SUITES) == {
        "traits", "facts", "recall", "altitude", "consultant", "inquiry",
    }
    assert suites.SUITES["traits"].needs_eval_gen is False
    assert suites.SUITES["consultant"].needs_eval_gen is True
    assert suites.SUITES["recall"].needs_scratch is True
    assert suites.SUITES["traits"].needs_scratch is False
    assert suites.SUITES["inquiry"].needs_eval_gen is False


@pytest.mark.asyncio
async def test_each_eval_case_uses_the_evaluation_model_route(
    migrated_db, monkeypatch,
):
    from app.llm import candidates
    from app.llm.client import resolve_structured_llm_config

    evaluation_config = {
        "base_url": "https://eval-model.test/v1",
        "api_key": "eval-key",
        "model": "eval-routed-model",
    }
    monkeypatch.setattr(
        candidates,
        "resolve_for_scenario",
        lambda scenario: evaluation_config if scenario == "evaluation" else {},
    )

    async def run_case(_case):
        return {
            "model": resolve_structured_llm_config(stage="trait")["model"],
        }

    suite = suites.Suite(
        key="route-test",
        load=lambda: [{}],
        run=run_case,
        name_of=lambda _case, _seq: "route-test",
        status_of=lambda _result: "pass",
        aggregate=lambda results: {"total": len(results)},
        needs_eval_gen=False,
        needs_scratch=False,
    )

    result = await stream._run_one(suite, {}, 0)

    assert result["result"]["model"] == "eval-routed-model"


@pytest.mark.asyncio
async def test_stream_traits_happy(migrated_db, monkeypatch):
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        _record_ok(system_prompt)                       # mimic real client tracing
        return {"O": {"score": 90, "confidence": 0.9,
                      "basis": "stable_self_statement", "evidence": "experimental"},
                "C": None, "E": None, "A": None, "N": None}
    monkeypatch.setattr("app.model_loop.traits.chat_json", fake_chat_json)

    frames = _capture(monkeypatch)
    await stream.main("traits")

    assert frames[0]["type"] == "run" and frames[0]["suite"] == "traits"
    assert frames[0]["total"] >= 1
    assert frames[-1]["type"] == "done" and frames[-1]["status"] == "done"
    assert "pass" in frames[-1]["aggregate"]

    cases = [f for f in frames if f["type"] == "case"]
    assert cases[0]["status"] == "pass"                 # O high, others null
    assert any(f["type"] == "trace" for f in frames)    # extraction call captured


@pytest.mark.asyncio
async def test_stream_error_when_model_unconfigured(migrated_db, monkeypatch):
    async def boom(system_prompt, user_prompt="", **kw):
        from app.llm.client import _record_llm_call
        _record_llm_call({"stage": "trait", "model": None, "status": "error",
                          "error": "unconfigured", "system_prompt": system_prompt,
                          "user_prompt": "", "response": "", "prompt_tokens": 0,
                          "completion_tokens": 0, "duration_ms": 0})
        raise RuntimeError("model not configured")
    monkeypatch.setattr("app.model_loop.traits.chat_json", boom)

    frames = _capture(monkeypatch)
    await stream.main("traits")

    cases = [f for f in frames if f["type"] == "case"]
    assert cases and all(c["status"] == "error" for c in cases)
    assert "model not configured" in cases[0]["error"]
    assert frames[-1]["status"] == "error"
    assert any(f["type"] == "trace" for f in frames)    # failed call still traced


@pytest.mark.asyncio
async def test_stream_recall_scratch_isolates_real_db(migrated_db, monkeypatch):
    async def fake_embed(text):
        t = text.lower()
        return [1.0, 0.0] if ("offer" in t or "job" in t) else [0.0, 1.0]
    monkeypatch.setattr("app.chat.ingest.embed", fake_embed)
    monkeypatch.setattr("app.chat.retrieval.embed", fake_embed)

    frames = _capture(monkeypatch)
    await stream.main("recall")

    assert [f for f in frames if f["type"] == "case"]   # ran at least one case
    from app.store import memory
    assert memory.max_turn() == -1                       # real DB never touched


@pytest.mark.asyncio
async def test_each_eval_case_pins_and_traces_one_prompt_release(migrated_db):
    workspace = service.get_workspace()
    prompt = next(
        item for item in workspace["prompts"]
        if item["key"] == "traits.ocean.extract"
    )
    release_a_content = "EVAL RELEASE A\n" + prompt["draft_content"]
    workspace = service.save_draft(
        prompt["key"], release_a_content, workspace["workspace_revision"],
    )
    published_a = service.publish(workspace["workspace_revision"], "eval A")
    release_a = published_a["active_release"]
    workspace = service.save_draft(
        prompt["key"],
        "EVAL RELEASE B\n" + release_a_content,
        published_a["workspace_revision"],
    )
    seen = []

    async def run_case(_case):
        seen.append(runtime.resolve(prompt["key"], "fallback"))
        service.publish(workspace["workspace_revision"], "eval B")
        seen.append(runtime.resolve(prompt["key"], "fallback"))
        _record_ok(seen[-1])
        return {"ok": True}

    suite = suites.Suite(
        key="pin-test",
        load=lambda: [{}],
        run=run_case,
        name_of=lambda _case, _seq: "pin-test",
        status_of=lambda _result: "pass",
        aggregate=lambda results: {"total": len(results)},
        needs_eval_gen=False,
        needs_scratch=False,
    )

    result = await stream._run_one(suite, {}, 0)

    assert all("EVAL RELEASE A" in content for content in seen)
    assert all("EVAL RELEASE B" not in content for content in seen)
    assert result["_traces"][0]["params"]["prompt_release_id"] == release_a["id"]
    assert (
        result["_traces"][0]["params"]["prompt_release_version"]
        == release_a["version"]
    )
