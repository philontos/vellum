from dataclasses import replace

from fastapi.testclient import TestClient

from app.auth import accounts
from app.main import create_app
from app.prompts import runtime, service
from app.prompts.catalog import PromptDefinition
from app.prompts.db import get_conn


def _client():
    return TestClient(create_app())


def _prompt(workspace: dict, key: str) -> dict:
    return next(item for item in workspace["prompts"] if item["key"] == key)


def test_lists_every_builtin_prompt_as_an_unpublished_workspace(migrated_db):
    response = _client().get("/admin/prompts")

    assert response.status_code == 200
    body = response.json()
    keys = {item["key"] for item in body["prompts"]}
    assert {
        "chat.neutral.voice",
        "chat.response_protocol",
        "chat.time_context",
        "memory.summary",
        "memory.dossier",
        "memory.facts.integrate",
        "memory.facts.compact",
        "traits.ocean.extract",
        "traits.mbti.extract",
        "traits.schwartz.extract",
        "traits.regulatory_focus.extract",
        "tool.web_search.description",
        "llm.json_only_hint",
    } <= keys
    assert body["workspace_revision"] == 0
    assert body["active_release"] is None
    assert body["has_unpublished_changes"] is False
    assert body["releases"] == []
    assert all(item["draft_content"] == item["published_content"] for item in body["prompts"])
    summary = _prompt(body, "memory.summary")
    assert set(summary["documentation"]) == {"en", "zh"}
    assert summary["documentation"]["en"]["usage"]
    assert summary["documentation"]["zh"]["runtime"]
    assert len(summary["documentation"]["en"]["editing_guidance"]) >= 2


def test_saves_a_draft_without_changing_runtime_then_publishes_one_atomic_release(migrated_db):
    client = _client()
    initial = client.get("/admin/prompts").json()
    current = _prompt(initial, "memory.summary")
    changed = current["draft_content"].replace("Summarize", "CUSTOM Summarize", 1)

    saved = client.put(
        "/admin/prompts/memory.summary/draft",
        json={"content": changed, "expected_revision": 0},
    )

    assert saved.status_code == 200
    draft_workspace = saved.json()
    assert draft_workspace["workspace_revision"] == 1
    assert draft_workspace["has_unpublished_changes"] is True
    assert _prompt(draft_workspace, "memory.summary")["is_modified"] is True
    assert "CUSTOM" not in runtime.active_snapshot().contents["memory.summary"]

    published = client.post(
        "/admin/prompts/publish",
        json={"expected_revision": 1, "note": "Tune summary wording"},
    )

    assert published.status_code == 200
    workspace = published.json()
    assert workspace["active_release"]["version"] == 1
    assert workspace["active_release"]["note"] == "Tune summary wording"
    assert workspace["has_unpublished_changes"] is False
    assert runtime.active_snapshot().contents["memory.summary"] == changed
    with get_conn() as conn:
        item_count = conn.execute(
            "SELECT COUNT(*) AS n FROM prompt_release_items WHERE release_id = ?",
            (workspace["active_release"]["id"],),
        ).fetchone()["n"]
    assert item_count == len([
        prompt for prompt in workspace["prompts"] if prompt["editable"]
    ])


def test_invalid_draft_can_be_saved_but_cannot_be_published(migrated_db):
    client = _client()

    saved = client.put(
        "/admin/prompts/memory.summary/draft",
        json={"content": "Summarize this, but omit the template contract.", "expected_revision": 0},
    )

    assert saved.status_code == 200
    item = _prompt(saved.json(), "memory.summary")
    assert item["validation_errors"]

    published = client.post(
        "/admin/prompts/publish",
        json={"expected_revision": 1, "note": "broken"},
    )
    assert published.status_code == 422
    assert "memory.summary" in str(published.json()["detail"])
    assert runtime.active_snapshot().release_id is None


def test_rejects_stale_workspace_writes_and_unknown_prompt_keys(migrated_db):
    client = _client()
    content = _prompt(client.get("/admin/prompts").json(), "memory.summary")["draft_content"]
    assert client.put(
        "/admin/prompts/memory.summary/draft",
        json={"content": content + "\n", "expected_revision": 0},
    ).status_code == 200

    stale = client.put(
        "/admin/prompts/memory.summary/draft",
        json={"content": content, "expected_revision": 0},
    )
    missing = client.put(
        "/admin/prompts/not.real/draft",
        json={"content": "x", "expected_revision": 1},
    )

    assert stale.status_code == 409
    assert missing.status_code == 404


def test_loads_an_old_release_as_draft_before_republishing(migrated_db):
    client = _client()
    original = _prompt(client.get("/admin/prompts").json(), "memory.summary")["draft_content"]
    version_one = original.replace("Summarize", "VERSION ONE Summarize", 1)
    version_two = original.replace("Summarize", "VERSION TWO Summarize", 1)

    first_save = client.put(
        "/admin/prompts/memory.summary/draft",
        json={"content": version_one, "expected_revision": 0},
    ).json()
    first = client.post(
        "/admin/prompts/publish",
        json={"expected_revision": first_save["workspace_revision"], "note": "one"},
    ).json()
    first_release_id = first["active_release"]["id"]
    second_save = client.put(
        "/admin/prompts/memory.summary/draft",
        json={"content": version_two, "expected_revision": first["workspace_revision"]},
    ).json()
    second = client.post(
        "/admin/prompts/publish",
        json={"expected_revision": second_save["workspace_revision"], "note": "two"},
    ).json()

    restored = client.post(
        f"/admin/prompts/releases/{first_release_id}/restore",
        json={"expected_revision": second["workspace_revision"]},
    )

    assert restored.status_code == 200
    workspace = restored.json()
    assert workspace["active_release"]["version"] == 2
    assert _prompt(workspace, "memory.summary")["draft_content"] == version_one
    assert _prompt(workspace, "memory.summary")["published_content"] == version_two
    assert workspace["has_unpublished_changes"] is True


def test_prompt_management_is_owner_only_but_legacy_mode_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    accounts.create_user("owner", "Owner", "a sufficiently long password", role="owner")
    accounts.create_user("member", "Member", "another sufficiently long password")

    owner = _client()
    member = _client()
    assert owner.post(
        "/auth/login",
        json={"username": "owner", "password": "a sufficiently long password"},
    ).status_code == 200
    assert member.post(
        "/auth/login",
        json={"username": "member", "password": "another sufficiently long password"},
    ).status_code == 200

    assert owner.get("/admin/prompts").status_code == 200
    assert member.get("/admin/prompts").status_code == 403


def test_protocol_prompts_are_visible_but_cannot_be_edited(migrated_db):
    client = _client()
    workspace = client.get("/admin/prompts").json()
    protocol = _prompt(workspace, "llm.json_only_hint")

    response = client.put(
        "/admin/prompts/llm.json_only_hint/draft",
        json={
            "content": protocol["draft_content"] + " changed",
            "expected_revision": workspace["workspace_revision"],
        },
    )

    assert protocol["editable"] is False
    assert response.status_code == 403


def test_old_releases_stay_immutable_and_publications_are_audited(migrated_db):
    client = _client()
    workspace = client.get("/admin/prompts").json()
    original = _prompt(workspace, "memory.summary")["draft_content"]
    first_content = original.replace("Summarize", "FIRST Summarize", 1)
    second_content = original.replace("Summarize", "SECOND Summarize", 1)

    workspace = client.put(
        "/admin/prompts/memory.summary/draft",
        json={"content": first_content, "expected_revision": 0},
    ).json()
    workspace = client.post(
        "/admin/prompts/publish",
        json={"expected_revision": workspace["workspace_revision"], "note": "first"},
    ).json()
    first_release = workspace["active_release"]["id"]
    workspace = client.put(
        "/admin/prompts/memory.summary/draft",
        json={
            "content": second_content,
            "expected_revision": workspace["workspace_revision"],
        },
    ).json()
    client.post(
        "/admin/prompts/publish",
        json={"expected_revision": workspace["workspace_revision"], "note": "second"},
    )

    with get_conn() as conn:
        first_row = conn.execute(
            "SELECT content FROM prompt_release_items "
            "WHERE release_id = ? AND prompt_key = 'memory.summary'",
            (first_release,),
        ).fetchone()
        actions = [
            row["action"]
            for row in conn.execute(
                "SELECT action FROM prompt_audit_events ORDER BY id"
            ).fetchall()
        ]
    assert first_row["content"] == first_content
    assert actions == ["draft_saved", "published", "draft_saved", "published"]


def test_publication_advances_revision_and_includes_new_catalog_prompts(
    migrated_db, monkeypatch,
):
    """A code upgrade must not leave the active release as a partial snapshot."""
    baseline = service.publish(0, "baseline")
    original_definitions = service.definitions()
    added = PromptDefinition(
        key="chat.added_later",
        name="Added later",
        description="Simulates a Prompt introduced by a later deployment.",
        category="chat",
        default_content="A new deployment-wide prompt.",
    )
    monkeypatch.setattr(
        service, "definitions", lambda: (*original_definitions, added),
    )

    upgraded = service.get_workspace()
    published = service.publish(
        upgraded["workspace_revision"], "complete upgraded catalog",
    )

    assert baseline["workspace_revision"] == 1
    assert upgraded["has_unpublished_changes"] is True
    assert _prompt(upgraded, added.key)["is_modified"] is True
    assert published["active_release"]["version"] == 2
    assert published["workspace_revision"] == 2
    with get_conn() as conn:
        item = conn.execute(
            "SELECT content FROM prompt_release_items "
            "WHERE release_id = ? AND prompt_key = ?",
            (published["active_release"]["id"], added.key),
        ).fetchone()
    assert item["content"] == added.default_content


def test_documentation_changes_do_not_create_or_modify_prompt_releases(
    migrated_db, monkeypatch,
):
    baseline = service.publish(0, "baseline")
    original_definitions = service.definitions()
    original = original_definitions[0]
    changed_documentation = replace(
        original.documentation,
        en=replace(
            original.documentation.en,
            usage=original.documentation.en.usage + " Documentation-only update.",
        ),
    )
    changed = replace(original, documentation=changed_documentation)
    monkeypatch.setattr(
        service,
        "definitions",
        lambda: (changed, *original_definitions[1:]),
    )
    monkeypatch.setattr(
        runtime,
        "definitions",
        lambda: (changed, *original_definitions[1:]),
    )

    workspace = service.get_workspace()
    republished = service.publish(workspace["workspace_revision"], "docs only")
    runtime_snapshot = runtime.active_snapshot()

    assert workspace["has_unpublished_changes"] is False
    assert "Documentation-only update" in _prompt(
        workspace, original.key,
    )["documentation"]["en"]["usage"]
    assert republished["active_release"] == baseline["active_release"]
    assert republished["workspace_revision"] == baseline["workspace_revision"]
    assert runtime_snapshot.contents[original.key] == original.default_content
    assert all(
        isinstance(content, str) for content in runtime_snapshot.contents.values()
    )
    assert all(
        "Documentation-only update" not in content
        for content in runtime_snapshot.contents.values()
    )
    with get_conn() as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM prompt_releases"
        ).fetchone()["n"] == 1
