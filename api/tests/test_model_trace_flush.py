import json

import pytest

from app.model_loop import runner
from app.store import traces


def test_flush_records_covered_span_in_params(migrated_db):
    """Background passes (trait/summary/dossier) cover a turn *range*, not one
    round. Record that span in params so the Traces panel can show 'turns 8–14'."""
    calls = [{"stage": "trait", "model": "m", "status": "ok", "system_prompt": "S",
              "user_prompt": "U", "response": "R", "prompt_tokens": 1,
              "completion_tokens": 1, "duration_ms": 1}]
    runner._flush_traces(calls, turn=14, start_turn=8)
    row = traces.list_recent(limit=1)[0]
    assert row["turn"] == 14                         # end of the span (the trigger turn)
    params = json.loads(row["params"])
    assert params["from"] == 8 and params["to"] == 14


def test_flush_stamps_one_batch_id_across_a_passs_calls(migrated_db):
    """A single pass can emit several LLM calls (e.g. one per trait dimension).
    All its trace rows must share one batch id so the pass is an unambiguous
    group even under concurrent run_pending — not merely inferred from (stage,turn)."""
    calls = [
        {"stage": "trait", "model": "m", "status": "ok", "system_prompt": "S1",
         "user_prompt": "U", "response": "R1", "prompt_tokens": 1,
         "completion_tokens": 1, "duration_ms": 1},
        {"stage": "trait", "model": "m", "status": "ok", "system_prompt": "S2",
         "user_prompt": "U", "response": "R2", "prompt_tokens": 1,
         "completion_tokens": 1, "duration_ms": 1},
    ]
    runner._flush_traces(calls, turn=11, start_turn=0, batch="trait:11:abcd1234")
    batches = {json.loads(r["params"])["batch"] for r in traces.list_recent(limit=10)}
    assert batches == {"trait:11:abcd1234"}          # both rows tagged with the same pass id


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


@pytest.mark.asyncio
async def test_run_concern_stamps_a_stage_scoped_batch_per_pass(migrated_db, monkeypatch):
    """run_pending must mint a batch id for each pass it fires and stamp it on the
    flushed traces, so a pass is identifiable without inferring from (stage, turn)."""
    from app.llm.client import _record_llm_call

    async def fake_job(start, end):
        _record_llm_call({"stage": "dossier", "model": "m", "status": "ok",
                          "system_prompt": "P", "user_prompt": "", "response": "D",
                          "prompt_tokens": 1, "completion_tokens": 1, "duration_ms": 1})

    monkeypatch.setattr(runner.config, "dossier_batch_m", lambda: 1)
    async def noop(s, e): pass
    monkeypatch.setattr(runner.facts, "run", noop)
    monkeypatch.setattr(runner.traits, "run", noop)
    monkeypatch.setattr(runner.summary, "run", noop)
    monkeypatch.setattr(runner.dossier, "run", fake_job)
    from app.store import memory
    memory.append_message("user", "x")
    await runner.run_pending()

    row = next(r for r in traces.list_recent(limit=10) if r["stage"] == "dossier")
    batch = json.loads(row["params"])["batch"]
    assert batch and batch.startswith("dossier:")    # present, stage-scoped, non-empty
