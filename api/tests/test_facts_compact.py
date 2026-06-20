"""Periodic compaction — the downward force on the board. reconcile only acts on
the new fact in hand, so residual old-vs-old redundancy never gets revisited.
Every X turns, facts.run scans the WHOLE board once and merges what reconcile
couldn't reach, so the active set can actually shrink, not only grow."""
import pytest

from app.model_loop import facts
from app.store import model


# --- _apply_compaction: deterministic apply (no LLM) ------------------------

def test_apply_compaction_merges_with_provenance(migrated_db):
    a = model.add_fact("based in Beijing", source_turn=1)
    b = model.add_fact("lives in Beijing", source_turn=4)
    model.add_fact("allergic to nuts", source_turn=2)

    facts._apply_compaction(
        {"merge": [{"ids": [a, b], "text": "lives in Beijing"}], "retire": []},
        model.active_facts(),
    )

    active = model.active_facts()
    assert sorted(f["text"] for f in active) == ["allergic to nuts", "lives in Beijing"]
    by_id = {f["id"]: f for f in model.all_facts()}
    assert by_id[a]["status"] == "superseded" and by_id[b]["status"] == "superseded"
    merged = next(f for f in active if f["text"] == "lives in Beijing")
    assert merged["source_turn"] == 4 and merged["id"] not in (a, b)


def test_apply_compaction_retires(migrated_db):
    keep = model.add_fact("allergic to nuts", source_turn=1)
    gone = model.add_fact("stale claim", source_turn=2)
    facts._apply_compaction({"merge": [], "retire": [gone]}, model.active_facts())
    ids = {f["id"] for f in model.active_facts()}
    assert keep in ids and gone not in ids


def test_apply_compaction_ignores_unknown_and_singleton(migrated_db):
    a = model.add_fact("a", source_turn=1)
    b = model.add_fact("b", source_turn=2)
    facts._apply_compaction(
        {"merge": [{"ids": [a, 9999], "text": "x"}, {"ids": [b], "text": "y"}], "retire": [8888]},
        model.active_facts(),
    )
    assert sorted(f["text"] for f in model.active_facts()) == ["a", "b"]


# --- compact(): one LLM call over the whole board ---------------------------

@pytest.mark.asyncio
async def test_compact_noop_under_two_facts(migrated_db, monkeypatch):
    model.add_fact("only one", source_turn=1)
    called: list = []

    async def fake(system_prompt, user_prompt="", **kw):
        called.append(kw.get("stage"))
        return {}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.compact()
    assert called == []                       # nothing to compact → no LLM call
    assert len(model.active_facts()) == 1


@pytest.mark.asyncio
async def test_compact_feeds_board_and_applies(migrated_db, monkeypatch):
    a = model.add_fact("based in Beijing", source_turn=1)
    b = model.add_fact("lives in Beijing", source_turn=2)
    seen: dict = {}

    async def fake(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        seen["stage"] = kw.get("stage")
        return {"merge": [{"ids": [a, b], "text": "lives in Beijing"}], "retire": []}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.compact()
    assert seen["stage"] == "compact"
    assert "based in Beijing" in seen["prompt"] and "lives in Beijing" in seen["prompt"]
    assert [f["text"] for f in model.active_facts()] == ["lives in Beijing"]


# --- run(): compaction is gated to every X turns inside the facts job --------

@pytest.mark.asyncio
async def test_run_compacts_on_cadence(migrated_db, monkeypatch):
    monkeypatch.setenv("VELLUM_FACTS_COMPACT_EVERY", "3")
    a = model.add_fact("lives in Beijing", source_turn=1)
    b = model.add_fact("based in Beijing", source_turn=2)
    model.add_fact("likes tea", source_turn=3)

    async def fake(system_prompt, user_prompt="", **kw):
        if kw.get("stage") == "compact":
            return {"merge": [{"ids": [a, b], "text": "lives in Beijing"}], "retire": []}
        return {"facts": []}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.run(start_turn=0, end_turn=6)   # 6 % 3 == 0 → compaction fires
    assert sorted(f["text"] for f in model.active_facts()) == ["likes tea", "lives in Beijing"]


@pytest.mark.asyncio
async def test_run_skips_compaction_off_cadence(migrated_db, monkeypatch):
    monkeypatch.setenv("VELLUM_FACTS_COMPACT_EVERY", "5")
    model.add_fact("lives in Beijing", source_turn=1)
    model.add_fact("based in Beijing", source_turn=2)
    seen: list = []

    async def fake(system_prompt, user_prompt="", **kw):
        seen.append(kw.get("stage"))
        return {"facts": []}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.run(start_turn=0, end_turn=7)   # 7 % 5 != 0 → no compaction
    assert "compact" not in seen
    assert len(model.active_facts()) == 2


@pytest.mark.asyncio
async def test_compaction_disabled_when_every_is_zero(migrated_db, monkeypatch):
    monkeypatch.setenv("VELLUM_FACTS_COMPACT_EVERY", "0")
    model.add_fact("a", source_turn=1)
    model.add_fact("b", source_turn=2)
    seen: list = []

    async def fake(system_prompt, user_prompt="", **kw):
        seen.append(kw.get("stage"))
        return {"facts": []}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.run(start_turn=0, end_turn=0)   # 0 would be a multiple, but 0 disables
    assert "compact" not in seen


@pytest.mark.asyncio
async def test_compaction_failure_does_not_break_run(migrated_db, monkeypatch):
    monkeypatch.setenv("VELLUM_FACTS_COMPACT_EVERY", "3")
    model.add_fact("a", source_turn=1)
    model.add_fact("b", source_turn=2)

    async def fake(system_prompt, user_prompt="", **kw):
        if kw.get("stage") == "compact":
            raise RuntimeError("LLM down")
        return {"facts": []}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.run(start_turn=0, end_turn=6)   # must not raise
    assert len(model.active_facts()) == 2
