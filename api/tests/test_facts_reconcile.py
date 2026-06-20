"""Write-time reconciliation: every newly-extracted fact is judged on its own
against the full active board (plus the conversation it came from), so the model
can accurately decide add vs duplicate vs update/supersede. This is what keeps the
board converged and contradiction-free instead of growing without bound."""
import pytest

from app.model_loop import facts
from app.store import memory, model


# --- _apply_decision: the deterministic apply step (no LLM) -----------------

def test_apply_decision_add_inserts(migrated_db):
    model.add_fact("allergic to penicillin", source_turn=1)
    active = model.active_facts()
    facts._apply_decision({"action": "add", "text": "lives in Shanghai", "retire": []}, active, 5)
    assert sorted(f["text"] for f in model.active_facts()) == ["allergic to penicillin", "lives in Shanghai"]
    sh = next(f for f in model.active_facts() if f["text"] == "lives in Shanghai")
    assert sh["source_turn"] == 5


def test_apply_decision_update_retires_and_adds(migrated_db):
    bj = model.add_fact("lives in Beijing", source_turn=1)
    active = model.active_facts()
    facts._apply_decision({"action": "update", "text": "lives in Shanghai", "retire": [bj]}, active, 7)
    assert [f["text"] for f in model.active_facts()] == ["lives in Shanghai"]
    by_id = {f["id"]: f for f in model.all_facts()}
    assert by_id[bj]["status"] == "superseded"


def test_apply_decision_duplicate_is_noop(migrated_db):
    model.add_fact("lives in Beijing", source_turn=1)
    active = model.active_facts()
    facts._apply_decision({"action": "duplicate", "text": "lives in Beijing", "retire": []}, active, 9)
    assert [f["text"] for f in model.active_facts()] == ["lives in Beijing"]


def test_apply_decision_ignores_unknown_retire_and_dup_add(migrated_db):
    model.add_fact("a", source_turn=1)
    active = model.active_facts()
    # text duplicates a survivor (skip add) and the retire id doesn't exist (ignore)
    facts._apply_decision({"action": "add", "text": "a", "retire": [9999]}, active, 5)
    assert [f["text"] for f in model.active_facts()] == ["a"]


# --- reconcile_one: one focused LLM call per new fact -----------------------

@pytest.mark.asyncio
async def test_reconcile_one_cold_board_adds_without_llm(migrated_db, monkeypatch):
    called: list = []

    async def fake(system_prompt, user_prompt="", **kw):
        called.append(kw.get("stage"))
        return {}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.reconcile_one("lives in Beijing", "span text", source_turn=3)
    assert [f["text"] for f in model.active_facts()] == ["lives in Beijing"]
    assert called == []   # nothing to reconcile against → no LLM call


@pytest.mark.asyncio
async def test_reconcile_one_feeds_context_and_supersedes(migrated_db, monkeypatch):
    bj = model.add_fact("lives in Beijing", source_turn=1)
    seen: dict = {}

    async def fake(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        seen["stage"] = kw.get("stage")
        return {"action": "update", "text": "lives in Shanghai", "retire": [bj]}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.reconcile_one("lives in Shanghai", "I moved to Shanghai last month", source_turn=6)

    assert [f["text"] for f in model.active_facts()] == ["lives in Shanghai"]
    assert seen["stage"] == "reconcile"
    assert "I moved to Shanghai last month" in seen["prompt"]   # raw conversation fed in
    assert "lives in Beijing" in seen["prompt"]                 # full board fed in
    assert "lives in Shanghai" in seen["prompt"]                # the new fact fed in


# --- run: extract, then reconcile each new fact -----------------------------

@pytest.mark.asyncio
async def test_run_extracts_then_reconciles_each(migrated_db, monkeypatch):
    bj = model.add_fact("lives in Beijing", source_turn=1)
    memory.append_message("user", "I moved to Shanghai and adopted a cat")

    async def fake(system_prompt, user_prompt="", **kw):
        if kw.get("stage") == "facts":
            return {"facts": ["lives in Shanghai", "has a cat"]}
        if kw.get("stage") == "reconcile":
            if "has a cat" in system_prompt:
                return {"action": "add", "text": "has a cat", "retire": []}
            return {"action": "update", "text": "lives in Shanghai", "retire": [bj]}
        return {}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.run(start_turn=0, end_turn=0)
    assert sorted(f["text"] for f in model.active_facts()) == ["has a cat", "lives in Shanghai"]


@pytest.mark.asyncio
async def test_run_per_fact_failure_is_isolated(migrated_db, monkeypatch):
    model.add_fact("seed fact", source_turn=1)
    memory.append_message("user", "two new things")

    async def fake(system_prompt, user_prompt="", **kw):
        if kw.get("stage") == "facts":
            return {"facts": ["fact one", "fact two"]}
        if kw.get("stage") == "reconcile":
            if "fact one" in system_prompt:
                raise RuntimeError("LLM down for this one")
            return {"action": "add", "text": "fact two", "retire": []}
        return {}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.run(start_turn=0, end_turn=0)   # must not raise
    texts = {f["text"] for f in model.active_facts()}
    assert "seed fact" in texts and "fact two" in texts
    assert "fact one" not in texts              # its reconcile failed, but the others survived
