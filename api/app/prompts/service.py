"""Prompt draft workspace, immutable releases, validation, and rollback staging."""
import hashlib
import json

from app.prompts import db
from app.prompts.catalog import PromptDefinition, definition_map, definitions
from app.prompts.validation import MAX_CONTENT_CHARS, validate


class UnknownPromptError(KeyError):
    pass


class UnknownReleaseError(KeyError):
    pass


class ReadOnlyPromptError(PermissionError):
    pass


class RevisionConflictError(RuntimeError):
    pass


class PublishValidationError(ValueError):
    def __init__(self, errors: dict[str, list[str]]):
        super().__init__("one or more prompts failed validation")
        self.errors = errors


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _active(conn) -> tuple[dict | None, dict[str, str]]:
    row = conn.execute(
        "SELECT r.* FROM prompt_workspace w "
        "LEFT JOIN prompt_releases r ON r.id = w.active_release_id WHERE w.id = 1"
    ).fetchone()
    if row is None or row["id"] is None:
        return None, {}
    release = dict(row)
    items = {
        item["prompt_key"]: item["content"]
        for item in conn.execute(
            "SELECT prompt_key, content FROM prompt_release_items WHERE release_id = ?",
            (row["id"],),
        )
    }
    return release, items


def load_active_release() -> tuple[dict | None, dict[str, str]]:
    db.run_migrations()
    with db.get_conn() as conn:
        return _active(conn)


def _prompt_view(
    definition: PromptDefinition,
    published: str,
    draft: str,
    updated_at: str | None,
    force_modified: bool = False,
) -> dict:
    return {
        "key": definition.key,
        "name": definition.name,
        "description": definition.description,
        "category": definition.category,
        "template_format": definition.template_format,
        "variables": list(definition.variables),
        "editable": definition.editable,
        "draft_content": draft,
        "published_content": published,
        "is_modified": force_modified or draft != published,
        "validation_errors": validate(definition, draft),
        "updated_at": updated_at,
    }


def _workspace(conn) -> dict:
    state = conn.execute("SELECT * FROM prompt_workspace WHERE id = 1").fetchone()
    active, active_items = _active(conn)
    drafts = {
        row["prompt_key"]: dict(row)
        for row in conn.execute("SELECT * FROM prompt_drafts")
    }
    prompts = []
    for definition in definitions():
        published = (
            active_items.get(definition.key, definition.default_content)
            if definition.editable else definition.default_content
        )
        draft_row = drafts.get(definition.key) if definition.editable else None
        draft = draft_row["content"] if draft_row else published
        prompts.append(_prompt_view(
            definition, published, draft,
            draft_row["updated_at"] if draft_row else None,
            force_modified=(
                definition.editable and active is not None
                and definition.key not in active_items
            ),
        ))
    releases = [
        {
            "id": row["id"],
            "version": row["version"],
            "note": row["note"],
            "published_at": row["published_at"],
            "is_active": active is not None and row["id"] == active["id"],
        }
        for row in conn.execute(
            "SELECT id, version, note, published_at FROM prompt_releases "
            "ORDER BY version DESC"
        )
    ]
    active_view = None if active is None else {
        "id": active["id"],
        "version": active["version"],
        "note": active["note"],
        "published_at": active["published_at"],
    }
    return {
        "workspace_revision": state["revision"],
        "active_release": active_view,
        "has_unpublished_changes": any(item["is_modified"] for item in prompts),
        "prompts": prompts,
        "releases": releases,
    }


def get_workspace() -> dict:
    db.run_migrations()
    with db.get_conn() as conn:
        # Keep state, active items, drafts, and release history on one SQLite
        # snapshot so the response's optimistic-lock revision matches its data.
        conn.execute("BEGIN")
        return _workspace(conn)


def _assert_revision(conn, expected: int) -> dict:
    state = conn.execute("SELECT * FROM prompt_workspace WHERE id = 1").fetchone()
    if state["revision"] != expected:
        raise RevisionConflictError(
            f"workspace changed: expected revision {expected}, current is {state['revision']}"
        )
    return dict(state)


def _audit(
    conn, action: str, *, actor_user_id: str | None = None,
    prompt_key: str | None = None, release_id: int | None = None,
    details: dict | None = None,
) -> None:
    conn.execute(
        "INSERT INTO prompt_audit_events"
        "(action, actor_user_id, prompt_key, release_id, details_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (action, actor_user_id, prompt_key, release_id,
         json.dumps(details or {}, ensure_ascii=False)),
    )


def save_draft(
    key: str, content: str, expected_revision: int,
    actor_user_id: str | None = None,
) -> dict:
    definition = definition_map().get(key)
    if definition is None:
        raise UnknownPromptError(key)
    if not definition.editable:
        raise ReadOnlyPromptError(key)
    if len(content) > MAX_CONTENT_CHARS:
        raise ValueError(f"draft exceeds {MAX_CONTENT_CHARS} characters")
    db.run_migrations()
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _assert_revision(conn, expected_revision)
        conn.execute(
            "INSERT INTO prompt_drafts(prompt_key, content) VALUES (?, ?) "
            "ON CONFLICT(prompt_key) DO UPDATE SET content = excluded.content, "
            "updated_at = datetime('now')",
            (key, content),
        )
        conn.execute(
            "UPDATE prompt_workspace SET revision = revision + 1, "
            "updated_at = datetime('now') WHERE id = 1"
        )
        _audit(conn, "draft_saved", actor_user_id=actor_user_id, prompt_key=key,
               details={"content_sha256": _hash(content)})
    return get_workspace()


def publish(
    expected_revision: int, note: str = "", actor_user_id: str | None = None,
) -> dict:
    note = note.strip()
    if len(note) > 500:
        raise ValueError("release note must be at most 500 characters")
    db.run_migrations()
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        state = _assert_revision(conn, expected_revision)
        active, active_items = _active(conn)
        drafts = {
            row["prompt_key"]: row["content"]
            for row in conn.execute("SELECT prompt_key, content FROM prompt_drafts")
        }
        editable_definitions = tuple(
            definition for definition in definitions() if definition.editable
        )
        snapshot: dict[str, str] = {}
        errors: dict[str, list[str]] = {}
        for definition in editable_definitions:
            content = drafts.get(
                definition.key,
                active_items.get(definition.key, definition.default_content),
            )
            snapshot[definition.key] = content
            item_errors = validate(definition, content)
            if item_errors:
                errors[definition.key] = item_errors
        if errors:
            raise PublishValidationError(errors)
        current = {
            definition.key: active_items.get(definition.key, definition.default_content)
            for definition in editable_definitions
        }
        active_is_complete = all(
            definition.key in active_items for definition in editable_definitions
        )
        if active is not None and active_is_complete and snapshot == current:
            return _workspace(conn)

        version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM prompt_releases"
        ).fetchone()["version"]
        cursor = conn.execute(
            "INSERT INTO prompt_releases"
            "(version, note, rollback_of_release_id, published_by) VALUES (?, ?, ?, ?)",
            (version, note, state["draft_source_release_id"], actor_user_id),
        )
        release_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO prompt_release_items"
            "(release_id, prompt_key, content, content_sha256) VALUES (?, ?, ?, ?)",
            [(release_id, key, content, _hash(content))
             for key, content in snapshot.items()],
        )
        conn.execute(
            "UPDATE prompt_workspace SET active_release_id = ?, "
            "draft_source_release_id = NULL, revision = revision + 1, "
            "updated_at = datetime('now') WHERE id = 1",
            (release_id,),
        )
        _audit(conn, "published", actor_user_id=actor_user_id, release_id=release_id,
               details={"version": version, "item_count": len(snapshot)})
    return get_workspace()


def restore_release(
    release_id: int, expected_revision: int, actor_user_id: str | None = None,
) -> dict:
    db.run_migrations()
    with db.get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        _assert_revision(conn, expected_revision)
        release = conn.execute(
            "SELECT id, version FROM prompt_releases WHERE id = ?", (release_id,)
        ).fetchone()
        if release is None:
            raise UnknownReleaseError(release_id)
        items = {
            row["prompt_key"]: row["content"]
            for row in conn.execute(
                "SELECT prompt_key, content FROM prompt_release_items WHERE release_id = ?",
                (release_id,),
            )
        }
        conn.execute("DELETE FROM prompt_drafts")
        conn.executemany(
            "INSERT INTO prompt_drafts(prompt_key, content) VALUES (?, ?)",
            [(definition.key, items.get(definition.key, definition.default_content))
             for definition in definitions() if definition.editable],
        )
        conn.execute(
            "UPDATE prompt_workspace SET revision = revision + 1, "
            "draft_source_release_id = ?, updated_at = datetime('now') WHERE id = 1",
            (release_id,),
        )
        _audit(conn, "release_loaded", actor_user_id=actor_user_id,
               release_id=release_id, details={"version": release["version"]})
    return get_workspace()
