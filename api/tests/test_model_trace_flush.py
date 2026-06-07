import pytest

from app.model_loop import runner
from app.store import traces


def test_flush_writes_one_trace_per_captured_call(migrated_db):
    calls = [
        {"stage": "trait", "model": "m", "status": "ok", "system_prompt": "SYS",
         "user_prompt": "U", "response": "RESP", "reasoning": "WHY", "prompt_tokens": 5,
         "completion_tokens": 6, "duration_ms": 7},
        {"stage": "facts", "model": "m", "status": "http_error", "error": "boom",
         "system_prompt": "S2", "user_prompt": "", "response": "errbody",
         "prompt_tokens": 0, "completion_tokens": 0, "duration_ms": 1},
    ]
    runner._flush_traces(calls, turn=4)
    rows = traces.list_recent(limit=10)
    assert {r["stage"] for r in rows} == {"trait", "facts"}
    trait_row = next(r for r in rows if r["stage"] == "trait")
    assert "SYS" in trait_row["prompt"] and trait_row["output"] == "RESP"
    assert trait_row["reasoning"] == "WHY"        # reasoning captured
    assert trait_row["completion_tokens"] == 6
    facts_row = next(r for r in rows if r["stage"] == "facts")
    assert facts_row["reasoning"] is None          # no reasoning → NULL


@pytest.mark.asyncio
async def test_run_concern_flushes_job_calls(migrated_db, monkeypatch):
    from app.llm.client import capture_llm_calls

    async def fake_job(start, end):
        # simulate the client recording a call mid-job
        from app.llm.client import _record_llm_call
        _record_llm_call({"stage": "dossier", "model": "m", "status": "ok",
                          "system_prompt": "P", "user_prompt": "", "response": "D",
                          "prompt_tokens": 1, "completion_tokens": 1, "duration_ms": 1})

    monkeypatch.setattr(runner.config, "dossier_batch_m", lambda: 1)
    # only run the dossier concern by giving the others a no-op
    async def noop(s, e): pass
    monkeypatch.setattr(runner.facts, "run", noop)
    monkeypatch.setattr(runner.traits, "run", noop)
    monkeypatch.setattr(runner.summary, "run", noop)
    monkeypatch.setattr(runner.dossier, "run", fake_job)
    from app.store import memory
    memory.append_message("user", "x")
    await runner.run_pending()
    assert any(r["stage"] == "dossier" and r["output"] == "D"
               for r in traces.list_recent(limit=10))
