import pytest

from app.model_loop import dossier
from app.store import memory, model, portrait_claims


def test_dossier_prompt_keeps_current_state_in_the_snapshot_layer():
    assert "Current state belongs in user-state snapshots" in dossier._EVIDENCE_PROMPT
    assert "do not add or update it as a portrait claim" in dossier._EVIDENCE_PROMPT


def test_dossier_rejects_new_current_state_claims(migrated_db):
    plan = {
        "update": [],
        "retire": [],
        "add": [{
            "claim_type": "current_state",
            "text": "Feels disappointed today.",
            "basis": "explicit",
            "evidence": [{"turn": 0, "quote": "disappointed today"}],
        }],
    }

    dossier._apply_changeset(
        plan, active=[], user_evidence={0: "I am disappointed today"},
    )

    assert portrait_claims.active() == []


@pytest.mark.asyncio
async def test_dossier_extracts_grounded_claims_then_renders_without_raw_conversation(
    migrated_db, monkeypatch,
):
    calls = []

    async def fake_chat_json(system_prompt, user_prompt="", stage="", **kw):
        calls.append({"system": system_prompt, "user": user_prompt, "stage": stage})
        if stage == "dossier_evidence":
            assert "I compare the trade-offs before major decisions" in user_prompt
            assert "You decide impulsively" in user_prompt
            return {
                "update": [],
                "retire": [],
                "add": [{
                    "claim_type": "decision_style",
                    "text": "Compares trade-offs before major decisions.",
                    "basis": "explicit",
                    "evidence": [{
                        "turn": 0,
                        "quote": "I compare the trade-offs before major decisions",
                    }],
                }],
            }
        assert stage == "dossier_render"
        assert "semantic support" in system_prompt
        assert "Compares trade-offs before major decisions." in user_prompt
        assert "Leads a ten-person engineering team." in user_prompt
        assert "You decide impulsively" not in user_prompt
        assert "LEGACY ASSISTANT VERDICT" not in user_prompt
        return {"dossier": "Compares trade-offs before making major decisions."}

    monkeypatch.setattr(dossier, "chat_json", fake_chat_json)
    model.set_dossier("LEGACY ASSISTANT VERDICT")
    model.add_fact("Leads a ten-person engineering team.", source_turn=0)
    memory.append_message("user", "I compare the trade-offs before major decisions")
    memory.append_message("assistant", "You decide impulsively")

    await dossier.run(start_turn=0, end_turn=1)

    assert [call["stage"] for call in calls] == ["dossier_evidence", "dossier_render"]
    assert model.get_dossier() == "Compares trade-offs before making major decisions."
    claims = portrait_claims.active()
    assert len(claims) == 1
    assert claims[0]["claim_type"] == "decision_style"
    assert claims[0]["source_turn"] == 0


@pytest.mark.asyncio
async def test_dossier_rejects_assistant_or_unquoted_evidence_before_render(
    migrated_db, monkeypatch,
):
    render_prompts = []

    async def fake_chat_json(system_prompt, user_prompt="", stage="", **kw):
        if stage == "dossier_evidence":
            return {
                "update": [],
                "retire": [],
                "add": [
                    {
                        "claim_type": "current_state",
                        "text": "Has decided to leave.",
                        "basis": "explicit",
                        "evidence": [{"turn": 1, "quote": "You have decided to leave"}],
                    },
                    {
                        "claim_type": "pattern",
                        "text": "Always avoids conflict.",
                        "basis": "inferred",
                        "evidence": [{"turn": 0, "quote": "I might leave"}],
                    },
                ],
            }
        render_prompts.append(user_prompt)
        return {"dossier": "Keeps durable facts grounded."}

    monkeypatch.setattr(dossier, "chat_json", fake_chat_json)
    model.add_fact("Works as an engineering lead.", source_turn=0)
    memory.append_message("user", "I might leave")
    memory.append_message("assistant", "You have decided to leave")

    await dossier.run(0, 1)

    assert portrait_claims.active() == []
    assert "Has decided to leave" not in render_prompts[0]
    assert "Always avoids conflict" not in render_prompts[0]


@pytest.mark.asyncio
async def test_dossier_updates_and_retires_claims_from_user_grounded_corrections(
    migrated_db, monkeypatch,
):
    old = portrait_claims.add(
        claim_type="decision_style",
        text="Thinks the product is low quality.",
        basis="inferred",
        evidence=[
            {"turn": 2, "quote": "the result feels discounted"},
            {"turn": 4, "quote": "the category has natural traffic"},
        ],
        source_turn=4,
    )
    gone = portrait_claims.add(
        claim_type="current_state",
        text="Has decided to resign.",
        basis="inferred",
        evidence=[
            {"turn": 2, "quote": "I am considering leaving"},
            {"turn": 4, "quote": "I feel sidelined"},
        ],
        source_turn=4,
    )

    async def fake_chat_json(system_prompt, user_prompt="", stage="", **kw):
        if stage == "dossier_evidence":
            return {
                "update": [{
                    "id": old,
                    "claim_type": "decision_style",
                    "text": "Does not consider the product low; discounts its results for category lift.",
                    "basis": "explicit",
                    "evidence": [{
                        "turn": 5,
                        "quote": "I do not think it is low; I think the result should be discounted",
                    }],
                }],
                "retire": [{
                    "id": gone,
                    "basis": "explicit",
                    "evidence": [{
                        "turn": 5,
                        "quote": "I have not decided to leave",
                    }],
                }],
                "add": [],
            }
        return {"dossier": "Separates category lift from execution quality."}

    monkeypatch.setattr(dossier, "chat_json", fake_chat_json)
    for turn in range(5):
        memory.append_message("user" if turn % 2 == 0 else "assistant", f"old {turn}")
    memory.append_message(
        "user",
        "I do not think it is low; I think the result should be discounted. "
        "I have not decided to leave",
    )

    await dossier.run(5, 5)

    active = portrait_claims.active()
    assert [claim["text"] for claim in active] == [
        "Does not consider the product low; discounts its results for category lift."
    ]
    assert {claim["id"] for claim in portrait_claims.all() if claim["status"] == "superseded"} == {
        old, gone,
    }


@pytest.mark.asyncio
async def test_dossier_invalid_render_is_retryable_and_preserves_previous_portrait(
    migrated_db, monkeypatch,
):
    async def fake_chat_json(system_prompt, user_prompt="", stage="", **kw):
        if stage == "dossier_evidence":
            return {"update": [], "retire": [], "add": []}
        return {}

    monkeypatch.setattr(dossier, "chat_json", fake_chat_json)
    model.set_dossier("original portrait")
    model.add_fact("A durable anchor.")
    memory.append_message("user", "new evidence")

    with pytest.raises(ValueError, match="dossier"):
        await dossier.run(0, 0)

    assert model.get_dossier() == "original portrait"


@pytest.mark.asyncio
async def test_dossier_chunks_a_large_backfill_before_one_full_render(
    migrated_db, monkeypatch,
):
    stages = []
    evidence_inputs = []

    async def fake_chat_json(system_prompt, user_prompt="", stage="", **kw):
        stages.append(stage)
        if stage == "dossier_evidence":
            evidence_inputs.append(user_prompt)
            return {"update": [], "retire": [], "add": []}
        return {"dossier": "Rendered from the grounded board."}

    monkeypatch.setattr(dossier, "chat_json", fake_chat_json)
    model.add_fact("A durable anchor.")
    for turn in range(25):
        memory.append_message("user" if turn % 2 == 0 else "assistant", f"message {turn}")

    await dossier.run(0, 24)

    assert stages == ["dossier_evidence", "dossier_evidence", "dossier_render"]
    assert "message 23" in evidence_inputs[1]  # preceding assistant context overlaps


@pytest.mark.asyncio
async def test_dossier_clears_legacy_prose_when_no_grounded_source_survives(
    migrated_db, monkeypatch,
):
    async def fake_chat_json(system_prompt, user_prompt="", stage="", **kw):
        assert stage == "dossier_evidence"
        return {"update": [], "retire": [], "add": []}

    monkeypatch.setattr(dossier, "chat_json", fake_chat_json)
    model.set_dossier("unsupported legacy portrait")
    memory.append_message("user", "hello")

    await dossier.run(0, 0)

    assert model.get_dossier() == ""
