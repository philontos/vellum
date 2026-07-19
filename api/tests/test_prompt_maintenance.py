import pytest

from app.prompts import maintenance, service


def _prompt(workspace: dict, key: str) -> dict:
    return next(item for item in workspace["prompts"] if item["key"] == key)


def _publish_old_schwartz_release() -> dict:
    workspace = service.get_workspace()
    for key in maintenance.SCHWARTZ_V2_PROMPT_KEYS:
        item = _prompt(workspace, key)
        workspace = service.save_draft(
            key,
            "LEGACY SCHWARTZ MARKER\n" + item["draft_content"],
            workspace["workspace_revision"],
        )
    return service.publish(workspace["workspace_revision"], "legacy Schwartz")


def test_schwartz_prompt_status_uses_code_defaults_without_a_release(migrated_db):
    status = maintenance.schwartz_v2_status()

    assert status["active_release"] is None
    assert status["matches_code_v2"] is True
    assert status["pending_keys"] == []


def test_publish_schwartz_v2_preserves_every_other_published_prompt(migrated_db):
    old = _publish_old_schwartz_release()
    before = {
        item["key"]: item["published_content"]
        for item in old["prompts"]
        if item["key"] not in maintenance.SCHWARTZ_V2_PROMPT_KEYS
    }

    result = maintenance.publish_schwartz_v2(actor_user_id="owner-id")

    assert result["changed"] is True
    assert result["status"]["matches_code_v2"] is True
    workspace = service.get_workspace()
    assert workspace["active_release"]["version"] == 2
    assert {
        item["key"]: item["published_content"]
        for item in workspace["prompts"]
        if item["key"] not in maintenance.SCHWARTZ_V2_PROMPT_KEYS
    } == before


def test_publish_schwartz_v2_refuses_to_publish_unrelated_drafts(migrated_db):
    old = _publish_old_schwartz_release()
    workspace = service.save_draft(
        "chat.altitude",
        "UNRELATED PENDING DRAFT\n" + _prompt(old, "chat.altitude")["draft_content"],
        old["workspace_revision"],
    )

    with pytest.raises(maintenance.PendingPromptDraftsError, match="chat.altitude"):
        maintenance.publish_schwartz_v2(actor_user_id="owner-id")

    after = service.get_workspace()
    assert after["workspace_revision"] == workspace["workspace_revision"]
    assert after["active_release"] == old["active_release"]


def test_publish_inquiry_grounding_v2_updates_only_the_inquiry_prompts(
    migrated_db,
):
    workspace = service.get_workspace()
    for key in ("inquiry.controller", "inquiry.repair"):
        current = _prompt(workspace, key)
        legacy = "LEGACY INQUIRY MARKER\n" + current["draft_content"]
        workspace = service.save_draft(
            key, legacy, workspace["workspace_revision"],
        )
    old = service.publish(workspace["workspace_revision"], "legacy Inquiry")
    before = {
        item["key"]: item["published_content"]
        for item in old["prompts"]
        if item["key"] not in {"inquiry.controller", "inquiry.repair"}
    }

    result = maintenance.publish_inquiry_grounding_v2(actor_user_id="owner-id")

    assert result["changed"] is True
    assert result["status"]["matches_code_v2"] is True
    upgraded = service.get_workspace()
    for key in ("inquiry.controller", "inquiry.repair"):
        assert _prompt(upgraded, key)["published_content"] == (
            maintenance.definition_map()[key].default_content
        )
    assert {
        item["key"]: item["published_content"]
        for item in upgraded["prompts"]
        if item["key"] not in {"inquiry.controller", "inquiry.repair"}
    } == before
