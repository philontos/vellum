"""Board-aware integration: each new conversation span is absorbed in ONE LLM
call that sees the whole active board AND the span (anchored to its real date).
The model returns a changeset — add new facts, rewrite an existing one richer or
corrected (update), retire what no longer holds — so the board stays converged,
grounded, and contradiction-free instead of accreting near-duplicate fragments.

This replaces the old extract-then-reconcile-each pipeline: perception and
integration are a single board-aware step, which is what kills fragmentation
(the same fact restated each turn) and fabrication (inventing a year/age)."""
import pytest

from app.model_loop import facts
from app.store import memory, model


# --- _apply_changeset: the deterministic apply step (no LLM) -----------------

def test_apply_changeset_add_inserts(migrated_db):
    model.add_fact("allergic to penicillin", source_turn=1)
    active = model.active_facts()
    facts._apply_changeset({"add": ["lives in Shanghai"], "update": [], "retire": []}, active, 5)
    assert sorted(f["text"] for f in model.active_facts()) == ["allergic to penicillin", "lives in Shanghai"]
    sh = next(f for f in model.active_facts() if f["text"] == "lives in Shanghai")
    assert sh["source_turn"] == 5


def test_apply_changeset_update_rewrites_richer(migrated_db):
    tl = model.add_fact("用户是团队负责人", source_turn=1)
    active = model.active_facts()
    facts._apply_changeset(
        {"update": [{"id": tl, "text": "用户是团队负责人，不直接参与开发"}], "retire": [], "add": []},
        active, 7)
    assert [f["text"] for f in model.active_facts()] == ["用户是团队负责人，不直接参与开发"]
    by_id = {f["id"]: f for f in model.all_facts()}
    assert by_id[tl]["status"] == "superseded"
    fresh = next(f for f in model.active_facts())
    assert fresh["source_turn"] == 7 and fresh["id"] != tl


def test_apply_changeset_retire_supersedes(migrated_db):
    keep = model.add_fact("allergic to nuts", source_turn=1)
    gone = model.add_fact("目标是冲击3-1职级", source_turn=2)
    facts._apply_changeset({"retire": [gone], "update": [], "add": []}, model.active_facts(), 9)
    ids = {f["id"] for f in model.active_facts()}
    assert keep in ids and gone not in ids


def test_apply_changeset_skips_add_duplicating_survivor(migrated_db):
    model.add_fact("lives in Beijing", source_turn=1)
    active = model.active_facts()
    facts._apply_changeset({"add": ["lives in Beijing", "  "], "update": [], "retire": []}, active, 5)
    assert [f["text"] for f in model.active_facts()] == ["lives in Beijing"]


def test_apply_changeset_ignores_unknown_and_empty(migrated_db):
    a = model.add_fact("a", source_turn=1)
    active = model.active_facts()
    facts._apply_changeset(
        {"update": [{"id": 9999, "text": "x"}, {"id": a, "text": ""}],
         "retire": [8888], "add": [123]},
        active, 5)
    assert [f["text"] for f in model.active_facts()] == ["a"]   # nothing valid applied


def test_apply_changeset_update_and_retire_same_id_supersedes_once(migrated_db):
    a = model.add_fact("a", source_turn=1)
    active = model.active_facts()
    # update already retired this id; the later retire must not double-act or resurrect
    facts._apply_changeset(
        {"update": [{"id": a, "text": "a refined"}], "retire": [a], "add": []}, active, 6)
    assert [f["text"] for f in model.active_facts()] == ["a refined"]


def test_inferred_fact_requires_two_distinct_user_turns():
    evidence = {4: "I avoided the disagreement", 6: "I said yes to keep the peace"}
    one_turn = {
        "basis": "inferred",
        "evidence": [{"turn": 4, "quote": "avoided the disagreement"}],
    }
    two_turns = {
        "basis": "inferred",
        "evidence": [
            {"turn": 4, "quote": "avoided the disagreement"},
            {"turn": 6, "quote": "said yes to keep the peace"},
        ],
    }

    assert facts._evidence_source_turn(one_turn, evidence, facts._CHANGE_BASES) is None
    assert facts._evidence_source_turn(two_turns, evidence, facts._CHANGE_BASES) == 6


def test_bare_acknowledgement_is_not_substantive_confirmation():
    evidence = {2: "对", 3: "对，这是我换工作的主要原因"}
    weak = {
        "basis": "confirmed",
        "evidence": [{"turn": 2, "quote": "对"}],
    }
    substantive = {
        "basis": "confirmed",
        "evidence": [{"turn": 3, "quote": "这是我换工作的主要原因"}],
    }

    assert facts._evidence_source_turn(weak, evidence, facts._CHANGE_BASES) is None
    assert facts._evidence_source_turn(substantive, evidence, facts._CHANGE_BASES) == 3


# --- integrate: one board-aware LLM call per span ---------------------------

@pytest.mark.asyncio
async def test_integrate_cold_board_adds(migrated_db, monkeypatch):
    seen: dict = {}

    async def fake(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        seen["stage"] = kw.get("stage")
        return {
            "add": [{
                "text": "lives in Beijing",
                "basis": "explicit",
                "evidence": [{"turn": 3, "quote": "I live in Beijing"}],
            }],
            "update": [],
            "retire": [],
        }
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.integrate(
        "I live in Beijing", as_of_date="2026-06-21", source_turn=3,
        user_evidence={3: "I live in Beijing"},
    )
    assert [f["text"] for f in model.active_facts()] == ["lives in Beijing"]
    assert seen["stage"] == "facts"
    assert "I live in Beijing" in seen["prompt"]   # span fed in
    assert "2026-06-21" in seen["prompt"]          # date anchor fed in


@pytest.mark.asyncio
async def test_integrate_feeds_full_board_and_enriches(migrated_db, monkeypatch):
    tl = model.add_fact("用户是团队负责人", source_turn=1)
    model.add_fact("allergic to nuts", source_turn=2)
    seen: dict = {}

    async def fake(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        return {
            "update": [{
                "id": tl,
                "text": "用户是团队负责人，不直接参与开发",
                "basis": "explicit",
                "evidence": [{"turn": 8, "quote": "我是TL，但已经不写代码了"}],
            }],
            "retire": [],
            "add": [],
        }
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.integrate(
        "我是TL，但已经不写代码了", as_of_date="2026-06-21", source_turn=8,
        user_evidence={8: "我是TL，但已经不写代码了"},
    )

    texts = sorted(f["text"] for f in model.active_facts())
    assert texts == ["allergic to nuts", "用户是团队负责人，不直接参与开发"]
    # the WHOLE board was visible to the model (both facts, with ids)
    assert "用户是团队负责人" in seen["prompt"] and "allergic to nuts" in seen["prompt"]


# --- run: span -> integrate; compaction gated separately --------------------

@pytest.mark.asyncio
async def test_run_integrates_the_span(migrated_db, monkeypatch):
    bj = model.add_fact("lives in Beijing", source_turn=1)
    memory.append_message("user", "I moved to Shanghai and adopted a cat")

    async def fake(system_prompt, user_prompt="", **kw):
        if kw.get("stage") == "facts":
            return {
                "update": [{
                    "id": bj,
                    "text": "lives in Shanghai",
                    "basis": "explicit",
                    "evidence": [{"turn": 0, "quote": "I moved to Shanghai"}],
                }],
                "retire": [],
                "add": [{
                    "text": "has a cat",
                    "basis": "explicit",
                    "evidence": [{"turn": 0, "quote": "adopted a cat"}],
                }],
            }
        return {}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.run(start_turn=0, end_turn=0)
    assert sorted(f["text"] for f in model.active_facts()) == ["has a cat", "lives in Shanghai"]
    assert {f["source_turn"] for f in model.active_facts()} == {0}


@pytest.mark.asyncio
async def test_run_rejects_assistant_only_fact_evidence(migrated_db, monkeypatch):
    fid = model.add_fact("user may value autonomy", source_turn=0)
    memory.append_message("user", "I am considering changing jobs")       # turn 0
    memory.append_message("assistant", "You value autonomy above all")     # turn 1

    async def fake(system_prompt, user_prompt="", **kw):
        return {
            "update": [{
                "id": fid,
                "text": "user values autonomy above all",
                "basis": "explicit",
                "evidence": [{"turn": 1, "quote": "You value autonomy above all"}],
            }],
            "retire": [],
            "add": [],
        }

    monkeypatch.setattr(facts, "chat_json", fake)
    await facts.run(0, 1)

    assert [f["text"] for f in model.active_facts()] == ["user may value autonomy"]


@pytest.mark.asyncio
async def test_run_rejects_non_verbatim_user_evidence(migrated_db, monkeypatch):
    fid = model.add_fact("user may live in Beijing", source_turn=0)
    memory.append_message("user", "I might relocate someday")

    async def fake(system_prompt, user_prompt="", **kw):
        return {
            "update": [{
                "id": fid,
                "text": "user lives in Shanghai",
                "basis": "explicit",
                "evidence": [{"turn": 0, "quote": "I live in Shanghai"}],
            }],
            "retire": [],
            "add": [],
        }

    monkeypatch.setattr(facts, "chat_json", fake)
    await facts.run(0, 0)

    assert [f["text"] for f in model.active_facts()] == ["user may live in Beijing"]


@pytest.mark.asyncio
async def test_run_propagates_integrate_failure(migrated_db, monkeypatch):
    """A transient LLM failure must propagate so the runner does NOT advance the
    facts cursor — the span is retried next turn instead of silently lost. The
    board is left untouched."""
    model.add_fact("seed fact", source_turn=1)
    memory.append_message("user", "something new")

    async def fake(system_prompt, user_prompt="", **kw):
        if kw.get("stage") == "facts":
            raise RuntimeError("LLM down")
        return {}
    monkeypatch.setattr(facts, "chat_json", fake)

    with pytest.raises(RuntimeError):
        await facts.run(start_turn=0, end_turn=0)
    assert [f["text"] for f in model.active_facts()] == ["seed fact"]


@pytest.mark.asyncio
async def test_run_noop_on_empty_span(migrated_db, monkeypatch):
    """No messages in range -> no integration LLM call at all."""
    called: list = []

    async def fake(system_prompt, user_prompt="", **kw):
        called.append(kw.get("stage"))
        return {}
    monkeypatch.setattr(facts, "chat_json", fake)

    await facts.run(start_turn=0, end_turn=0)
    assert called == []
