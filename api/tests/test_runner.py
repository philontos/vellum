import pytest

from app.model_loop import runner
from app.store import memory


@pytest.mark.asyncio
async def test_facts_run_every_call_others_gated(migrated_db, monkeypatch):
    ran = {"facts": [], "trait": [], "summary": [], "dossier": []}

    async def mk(name):
        async def _job(start_turn, end_turn):
            ran[name].append((start_turn, end_turn))
        return _job
    monkeypatch.setattr(runner.facts, "run", await mk("facts"))
    monkeypatch.setattr(runner.traits, "run", await mk("trait"))
    monkeypatch.setattr(runner.summary, "run", await mk("summary"))
    monkeypatch.setattr(runner.dossier, "run", await mk("dossier"))
    monkeypatch.setattr(runner.config, "trait_batch_k", lambda: 3)
    monkeypatch.setattr(runner.config, "summary_span_s", lambda: 3)
    monkeypatch.setattr(runner.config, "dossier_batch_m", lambda: 100)

    for i in range(3):
        memory.append_message("user", f"m{i}")     # turns 0,1,2
    await runner.run_pending()

    assert ran["facts"] == [(0, 2)]                 # eager: catches up every call
    assert ran["trait"] == [(0, 2)]                 # gap 3 >= K(3) → ran
    assert ran["summary"] == [(0, 2)]               # gap 3 >= S(3) → ran
    assert ran["dossier"] == []                     # gap 3 < M(100) → skipped
    # cursors advanced for the ones that ran
    assert memory.get_cursor("trait") == 2 and memory.get_cursor("facts") == 2
    assert memory.get_cursor("dossier") == -1


@pytest.mark.asyncio
async def test_run_pending_idempotent(migrated_db, monkeypatch):
    ran = {"facts": 0}
    async def facts_job(s, e): ran["facts"] += 1
    async def noop(s, e): pass
    monkeypatch.setattr(runner.facts, "run", facts_job)
    monkeypatch.setattr(runner.traits, "run", noop)
    monkeypatch.setattr(runner.summary, "run", noop)
    monkeypatch.setattr(runner.dossier, "run", noop)
    memory.append_message("user", "x")
    await runner.run_pending()
    await runner.run_pending()          # no new turns → no-op
    assert ran["facts"] == 1


@pytest.mark.asyncio
async def test_one_failing_job_does_not_block_others(migrated_db, monkeypatch):
    async def boom(start_turn, end_turn):
        raise RuntimeError("trait broke")
    async def ok(start_turn, end_turn):
        pass
    monkeypatch.setattr(runner.traits, "run", boom)
    monkeypatch.setattr(runner.facts, "run", ok)
    monkeypatch.setattr(runner.summary, "run", ok)
    monkeypatch.setattr(runner.dossier, "run", ok)
    monkeypatch.setattr(runner.config, "trait_batch_k", lambda: 1)
    monkeypatch.setattr(runner.config, "summary_span_s", lambda: 1)
    monkeypatch.setattr(runner.config, "dossier_batch_m", lambda: 1)

    memory.append_message("user", "x")
    await runner.run_pending()                       # must not raise
    assert memory.get_cursor("trait") == -1          # failed → not advanced
    assert memory.get_cursor("summary") == 0         # ok → advanced
