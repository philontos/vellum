"""Guarded CLI for deployment-time Prompt schema upgrades."""
from __future__ import annotations

import argparse

from app import config
from app.auth import accounts
from app.prompts import service
from app.prompts.catalog import definition_map


SCHWARTZ_V2_PROMPT_KEYS = (
    "traits.schwartz.extract",
    "traits.schwartz.rubric",
)


class PendingPromptDraftsError(RuntimeError):
    """Publishing the upgrade would also release unrelated owner drafts."""


def _workspace_prompts(workspace: dict) -> dict[str, dict]:
    return {item["key"]: item for item in workspace["prompts"]}


def schwartz_v2_status() -> dict:
    workspace = service.get_workspace()
    prompts = _workspace_prompts(workspace)
    definitions = definition_map()
    return {
        "active_release": workspace["active_release"],
        "workspace_revision": workspace["workspace_revision"],
        "matches_code_v2": all(
            prompts[key]["published_content"] == definitions[key].default_content
            for key in SCHWARTZ_V2_PROMPT_KEYS
        ),
        "pending_keys": sorted(
            item["key"] for item in workspace["prompts"] if item["is_modified"]
        ),
    }


def publish_schwartz_v2(actor_user_id: str | None = None) -> dict:
    """Publish code-owned V2 Schwartz prompts while preserving all other prompts."""
    workspace = service.get_workspace()
    prompts = _workspace_prompts(workspace)
    definitions = definition_map()
    unrelated = sorted(
        item["key"]
        for item in workspace["prompts"]
        if item["is_modified"] and item["key"] not in SCHWARTZ_V2_PROMPT_KEYS
    )
    if unrelated:
        raise PendingPromptDraftsError(
            "unrelated unpublished Prompt drafts must be resolved first: "
            + ", ".join(unrelated)
        )
    if all(
        prompts[key]["published_content"] == definitions[key].default_content
        for key in SCHWARTZ_V2_PROMPT_KEYS
    ):
        return {"changed": False, "status": schwartz_v2_status()}

    for key in SCHWARTZ_V2_PROMPT_KEYS:
        expected = definitions[key].default_content
        current = _workspace_prompts(workspace)[key]
        if current["draft_content"] == expected:
            continue
        workspace = service.save_draft(
            key,
            expected,
            workspace["workspace_revision"],
            actor_user_id=actor_user_id,
        )
    service.publish(
        workspace["workspace_revision"],
        "Upgrade Schwartz extraction to signed V2 evidence",
        actor_user_id=actor_user_id,
    )
    status = schwartz_v2_status()
    if not status["matches_code_v2"]:
        raise RuntimeError("published Schwartz Prompt release does not match code V2")
    return {"changed": True, "status": status}


def _actor(username: str | None) -> tuple[str | None, str]:
    if config.auth_enabled():
        if not username:
            raise SystemExit("--username is required when VELLUM_AUTH_ENABLED=1")
        user = accounts.get_by_username(username)
        if user is None:
            raise SystemExit(f"unknown account: {username}")
        if user["status"] != "active" or user["role"] != "owner":
            raise SystemExit(f"active owner account required: {username}")
        return user["id"], user["username"]
    if username:
        raise SystemExit("--username is only valid when VELLUM_AUTH_ENABLED=1")
    return None, "legacy owner"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.prompts.maintenance")
    parser.add_argument("upgrade", choices=["schwartz-v2"])
    parser.add_argument("--username")
    parser.add_argument(
        "--apply", action="store_true",
        help="publish a new immutable release when active prompts differ from V2",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    actor_user_id, actor_label = _actor(args.username)
    status = schwartz_v2_status()
    release = status["active_release"]
    release_label = (
        "none" if release is None else f"{release['id']} (version {release['version']})"
    )
    print(f"Actor: {actor_label}")
    print(f"Active Prompt release: {release_label}")
    print(f"Schwartz prompts match code V2: {status['matches_code_v2']}")
    print("Pending Prompt drafts: " + (", ".join(status["pending_keys"]) or "none"))
    if not args.apply:
        print("DRY RUN: add --apply to publish the guarded Schwartz V2 upgrade.")
        return 0
    try:
        result = publish_schwartz_v2(actor_user_id=actor_user_id)
    except PendingPromptDraftsError as exc:
        raise SystemExit(str(exc)) from exc
    final = result["status"]["active_release"]
    if result["changed"]:
        print(f"Published Prompt release {final['id']} (version {final['version']}).")
    else:
        print("No change: the active Schwartz prompts already match code V2.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
