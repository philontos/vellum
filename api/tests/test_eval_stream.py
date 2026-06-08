"""evals.stream JSONL entrypoint + suites registry: happy path, graceful error
when the model is unconfigured, and recall through in-memory scratch (isolation)."""
import pytest

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
    assert set(suites.SUITES) == {"traits", "facts", "recall", "altitude", "consultant"}
    assert suites.SUITES["traits"].needs_eval_gen is False
    assert suites.SUITES["consultant"].needs_eval_gen is True
    assert suites.SUITES["recall"].needs_scratch is True
    assert suites.SUITES["traits"].needs_scratch is False


@pytest.mark.asyncio
async def test_stream_traits_happy(migrated_db, monkeypatch):
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        _record_ok(system_prompt)                       # mimic real client tracing
        return {"O": {"score": 90, "confidence": 0.9, "evidence": "x"},
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
