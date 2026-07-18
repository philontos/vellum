import pytest

from app.model_loop import rebuild, schwartz
from app.prompts import runtime
from app.store import memory, model


def _all_null():
    return {key: None for key in schwartz.VALUE_KEYS}


def _observation(
    key, *, direction="support", counterpart=None, episode=None, evidence=None,
):
    output = _all_null()
    output[key] = {
        "direction": direction,
        "strength": 0.85,
        "confidence": 0.8,
        "basis": "tradeoff",
        "episode": episode or f"episode for {key}",
        "evidence": evidence or f"evidence for {key}",
        "counterpart": counterpart,
    }
    return output


def _seed_history():
    for role, text in (
        ("user", "first choice"),
        ("assistant", "first reply"),
        ("user", "second choice"),
        ("assistant", "second reply"),
    ):
        memory.append_message(role, text)


def _seed_old_schwartz():
    model.set_trait(
        "schwartz",
        {"achievement": {"score": 80, "confidence": 0.7, "evidence": "old"}},
        sample_count=9,
    )
    model.add_trait_evidence([{
        "dimension": "schwartz",
        "subdimension": "achievement",
        "episode_key": "legacy-v1:achievement",
        "direction": "support",
        "strength": 0.6,
        "confidence": 0.7,
        "basis": "legacy",
        "episode": "legacy aggregate",
        "evidence": "old",
        "occurrences": 9,
        "model_version": "schwartz-v1-bridge",
    }])


def test_rebuild_preview_includes_the_final_partial_turn_batch(migrated_db):
    for role in ("user", "assistant", "user", "assistant", "user"):
        memory.append_message(role, role)

    preview = rebuild.preview_schwartz(batch_turns=2)

    assert preview == {
        "dimension": "schwartz",
        "first_turn": 0,
        "last_turn": 4,
        "live_messages": 5,
        "user_messages": 3,
        "batch_turns": 2,
        "spans": [(0, 1), (2, 3), (4, 4)],
    }


def test_rebuild_preview_excludes_soft_deleted_user_history(migrated_db):
    deleted = memory.append_message("user", "withdrawn")
    memory.append_message("assistant", "reply")
    memory.append_message("user", "still live")
    memory.soft_delete(deleted["turn"])

    preview = rebuild.preview_schwartz(batch_turns=1)

    assert preview["live_messages"] == 2
    assert preview["user_messages"] == 1
    assert preview["spans"] == [(2, 2)]


def test_rebuild_cli_is_a_read_only_preview_without_apply(migrated_db, monkeypatch, capsys):
    _seed_history()
    _seed_old_schwartz()

    async def must_not_run(**kwargs):
        raise AssertionError("dry-run must not extract or write")

    monkeypatch.setattr(rebuild, "rebuild_schwartz", must_not_run)
    monkeypatch.setattr(
        rebuild.store_db, "run_migrations",
        lambda: (_ for _ in ()).throw(AssertionError("dry-run must not migrate")),
    )

    assert rebuild.main(["schwartz", "--batch-turns", "2"]) == 0

    output = capsys.readouterr().out
    assert "DRY RUN" in output
    assert "2 extraction batches" in output
    assert model.get_trait("schwartz")["sample_count"] == 9


def test_rebuild_cli_requires_an_explicit_account_in_family_mode(
    migrated_db, monkeypatch,
):
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")

    with pytest.raises(SystemExit, match="--username is required"):
        rebuild.main(["schwartz"])


def test_rebuild_cli_checks_the_background_model_route(
    migrated_db, monkeypatch,
):
    _seed_history()
    seen = []

    def configured(**kwargs):
        seen.append(kwargs)
        return False

    monkeypatch.setattr(rebuild, "is_structured_llm_configured", configured)

    with pytest.raises(SystemExit, match="background modeling LLM"):
        rebuild.main(["schwartz", "--apply"])

    assert seen == [{"stage": "trait"}]


@pytest.mark.asyncio
async def test_rebuild_stages_everything_then_atomically_replaces_only_schwartz(
    migrated_db, monkeypatch,
):
    _seed_history()
    _seed_old_schwartz()
    model.set_trait("ocean", {"O": {"score": 70}}, sample_count=2)
    memory.advance_cursor("trait", 3)
    outputs = [
        _observation(
            "self_direction", counterpart="security", episode="choosing autonomy",
            evidence="first choice",
        ),
        _observation(
            "benevolence", episode="helping family", evidence="second choice",
        ),
    ]
    calls = []

    async def fake_extract(span, key, dim, old_content):
        calls.append((span, old_content))
        # The live row is untouched during every expensive LLM call.
        assert model.get_trait("schwartz")["content_json"]["achievement"]["score"] == 80
        return outputs[len(calls) - 1]

    monkeypatch.setattr(rebuild.traits, "_extract", fake_extract)

    result = await rebuild.rebuild_schwartz(
        batch_turns=2,
        snapshot=runtime.default_snapshot(),
    )

    current = model.get_trait("schwartz")
    assert current["sample_count"] == 2
    assert current["content_json"]["self_direction"]["priority"] is not None
    assert current["content_json"]["benevolence"]["priority"] is not None
    assert len(model.get_trait_history("schwartz")) == 2
    assert {row["episode"] for row in model.get_trait_evidence("schwartz")} == {
        "choosing autonomy", "helping family",
    }
    assert model.get_trait("ocean")["content_json"]["O"]["score"] == 70
    assert memory.get_cursor("trait") == 3
    assert result["batches"] == 2
    assert result["evidence_episodes"] == 2
    assert result["assessed_values"] == 2
    assert "first choice" in calls[0][0]
    assert "second choice" in calls[1][0]


@pytest.mark.asyncio
async def test_rebuild_discards_hallucinated_schwartz_quotes(
    migrated_db, monkeypatch,
):
    memory.append_message("user", "the actual choice")
    _seed_old_schwartz()

    async def fake_extract(span, key, dim, old_content):
        return _observation(
            "achievement", episode="invented episode", evidence="not in history",
        )

    monkeypatch.setattr(rebuild.traits, "_extract", fake_extract)

    result = await rebuild.rebuild_schwartz(
        batch_turns=1,
        snapshot=runtime.default_snapshot(),
    )

    assert result["evidence_episodes"] == 0
    assert model.get_trait_evidence("schwartz") == []
    assert model.get_trait("schwartz")["content_json"]["achievement"][
        "status"
    ] == "unobserved"


@pytest.mark.asyncio
async def test_rebuild_failure_preserves_the_entire_old_schwartz_model(
    migrated_db, monkeypatch,
):
    _seed_history()
    _seed_old_schwartz()
    old_current = model.get_trait("schwartz")
    old_history = model.get_trait_history("schwartz")
    old_evidence = model.get_trait_evidence("schwartz")
    calls = 0

    async def fails_on_second_batch(span, key, dim, old_content):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("provider failed")
        return _observation("self_direction")

    monkeypatch.setattr(rebuild.traits, "_extract", fails_on_second_batch)

    with pytest.raises(RuntimeError, match="provider failed"):
        await rebuild.rebuild_schwartz(
            batch_turns=2,
            snapshot=runtime.default_snapshot(),
        )

    assert model.get_trait("schwartz") == old_current
    assert model.get_trait_history("schwartz") == old_history
    assert model.get_trait_evidence("schwartz") == old_evidence


@pytest.mark.asyncio
async def test_rebuild_rejects_a_stale_v1_prompt_output_without_data_loss(
    migrated_db, monkeypatch,
):
    _seed_history()
    _seed_old_schwartz()
    old_current = model.get_trait("schwartz")

    async def stale_output(span, key, dim, old_content):
        output = _all_null()
        output["achievement"] = {
            "score": 78, "confidence": 0.8, "evidence": "old schema",
        }
        return output

    monkeypatch.setattr(rebuild.traits, "_extract", stale_output)

    with pytest.raises(ValueError, match="missing"):
        await rebuild.rebuild_schwartz(
            batch_turns=2,
            snapshot=runtime.default_snapshot(),
        )

    assert model.get_trait("schwartz") == old_current


@pytest.mark.asyncio
async def test_rebuild_refuses_to_overwrite_if_conversation_changes_mid_run(
    migrated_db, monkeypatch,
):
    _seed_history()
    _seed_old_schwartz()

    async def concurrent_message(span, key, dim, old_content):
        if memory.max_turn() == 3:
            memory.append_message("user", "arrived during rebuild")
        return _observation("self_direction")

    monkeypatch.setattr(rebuild.traits, "_extract", concurrent_message)

    with pytest.raises(rebuild.RebuildConflictError, match="history changed"):
        await rebuild.rebuild_schwartz(
            batch_turns=2,
            snapshot=runtime.default_snapshot(),
        )

    assert model.get_trait("schwartz")["content_json"]["achievement"]["score"] == 80
    assert model.get_trait("schwartz")["sample_count"] == 9


@pytest.mark.asyncio
async def test_rebuild_does_not_miss_a_message_arriving_between_guard_and_plan(
    migrated_db, monkeypatch,
):
    _seed_history()
    _seed_old_schwartz()
    real_preview = rebuild.preview_schwartz

    def message_after_preview(batch_turns):
        plan = real_preview(batch_turns)
        memory.append_message("user", "arrived at the planning boundary")
        return plan

    async def extract(span, key, dim, old_content):
        return _observation("self_direction")

    monkeypatch.setattr(rebuild, "preview_schwartz", message_after_preview)
    monkeypatch.setattr(rebuild.traits, "_extract", extract)

    with pytest.raises(rebuild.RebuildConflictError, match="history changed"):
        await rebuild.rebuild_schwartz(
            batch_turns=2,
            snapshot=runtime.default_snapshot(),
        )

    assert model.get_trait("schwartz")["sample_count"] == 9
