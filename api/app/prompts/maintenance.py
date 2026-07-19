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
INQUIRY_GROUNDING_V2_PROMPT_KEYS = (
    "inquiry.controller",
    "inquiry.repair",
)
CONSULTATION_V3_PROMPT_KEYS = (
    "chat.neutral.voice",
    "chat.altitude",
    "chat.response_protocol",
    "chat.trait_frame",
    "inquiry.controller",
    "inquiry.repair",
    "memory.dossier.evidence",
    "memory.dossier.render",
    "memory.facts.integrate",
    "memory.facts.compact",
    "traits.ocean.extract",
    "traits.mbti.extract",
    "traits.regulatory_focus.extract",
    "traits.schwartz.extract",
)


class PendingPromptDraftsError(RuntimeError):
    """Publishing the upgrade would also release unrelated owner drafts."""


def _workspace_prompts(workspace: dict) -> dict[str, dict]:
    return {item["key"]: item for item in workspace["prompts"]}


def _upgrade_status(
    keys: tuple[str, ...], *, match_key: str = "matches_code_v2",
) -> dict:
    workspace = service.get_workspace()
    prompts = _workspace_prompts(workspace)
    definitions = definition_map()
    return {
        "active_release": workspace["active_release"],
        "workspace_revision": workspace["workspace_revision"],
        match_key: all(
            prompts[key]["published_content"] == definitions[key].default_content
            for key in keys
        ),
        "pending_keys": sorted(
            item["key"] for item in workspace["prompts"] if item["is_modified"]
        ),
    }


def schwartz_v2_status() -> dict:
    return _upgrade_status(SCHWARTZ_V2_PROMPT_KEYS)


def inquiry_grounding_v2_status() -> dict:
    return _upgrade_status(INQUIRY_GROUNDING_V2_PROMPT_KEYS)


def consultation_v3_status() -> dict:
    return _upgrade_status(
        CONSULTATION_V3_PROMPT_KEYS, match_key="matches_code_v3",
    )


def _publish_code_defaults(
    keys: tuple[str, ...], *, note: str, actor_user_id: str | None = None,
    match_key: str = "matches_code_v2",
) -> dict:
    workspace = service.get_workspace()
    prompts = _workspace_prompts(workspace)
    definitions = definition_map()
    unrelated = sorted(
        item["key"]
        for item in workspace["prompts"]
        if item["is_modified"] and item["key"] not in keys
    )
    if unrelated:
        raise PendingPromptDraftsError(
            "unrelated unpublished Prompt drafts must be resolved first: "
            + ", ".join(unrelated)
        )
    if all(
        prompts[key]["published_content"] == definitions[key].default_content
        for key in keys
    ):
        return {
            "changed": False,
            "status": _upgrade_status(keys, match_key=match_key),
        }

    for key in keys:
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
        note,
        actor_user_id=actor_user_id,
    )
    status = _upgrade_status(keys, match_key=match_key)
    if not status[match_key]:
        raise RuntimeError("published Prompt release does not match code defaults")
    return {"changed": True, "status": status}


def publish_schwartz_v2(actor_user_id: str | None = None) -> dict:
    """Publish code-owned V2 Schwartz prompts while preserving all other prompts."""
    return _publish_code_defaults(
        SCHWARTZ_V2_PROMPT_KEYS,
        note="Upgrade Schwartz extraction to signed V2 evidence",
        actor_user_id=actor_user_id,
    )


def publish_inquiry_grounding_v2(actor_user_id: str | None = None) -> dict:
    """Publish the evidence-first Inquiry gate without changing other prompts."""
    return _publish_code_defaults(
        INQUIRY_GROUNDING_V2_PROMPT_KEYS,
        note="Upgrade Inquiry grounding and consultation gate to V2",
        actor_user_id=actor_user_id,
    )


def publish_consultation_v3(actor_user_id: str | None = None) -> dict:
    """Publish the user-state-first consultation prompts as one guarded release."""
    return _publish_code_defaults(
        CONSULTATION_V3_PROMPT_KEYS,
        note="Upgrade consultation, user-state, and Inquiry readiness prompts to V3",
        actor_user_id=actor_user_id,
        match_key="matches_code_v3",
    )


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
    parser.add_argument(
        "upgrade", choices=[
            "schwartz-v2", "inquiry-grounding-v2", "consultation-v3",
        ],
    )
    parser.add_argument("--username")
    parser.add_argument(
        "--apply", action="store_true",
        help="publish a new immutable release when active prompts differ from code",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    actor_user_id, actor_label = _actor(args.username)
    if args.upgrade == "consultation-v3":
        status = consultation_v3_status()
        publish_upgrade = publish_consultation_v3
        upgrade_label = "Consultation prompts"
        match_key = "matches_code_v3"
        version_label = "V3"
    elif args.upgrade == "inquiry-grounding-v2":
        status = inquiry_grounding_v2_status()
        publish_upgrade = publish_inquiry_grounding_v2
        upgrade_label = "Inquiry grounding prompts"
        match_key = "matches_code_v2"
        version_label = "V2"
    else:
        status = schwartz_v2_status()
        publish_upgrade = publish_schwartz_v2
        upgrade_label = "Schwartz prompts"
        match_key = "matches_code_v2"
        version_label = "V2"
    release = status["active_release"]
    release_label = (
        "none" if release is None else f"{release['id']} (version {release['version']})"
    )
    print(f"Actor: {actor_label}")
    print(f"Active Prompt release: {release_label}")
    print(f"{upgrade_label} match code {version_label}: {status[match_key]}")
    print("Pending Prompt drafts: " + (", ".join(status["pending_keys"]) or "none"))
    if not args.apply:
        print(f"DRY RUN: add --apply to publish the guarded {version_label} upgrade.")
        return 0
    try:
        result = publish_upgrade(actor_user_id=actor_user_id)
    except PendingPromptDraftsError as exc:
        raise SystemExit(str(exc)) from exc
    final = result["status"]["active_release"]
    if result["changed"]:
        print(f"Published Prompt release {final['id']} (version {final['version']}).")
    else:
        print(
            f"No change: the active {upgrade_label.lower()} already match "
            f"code {version_label}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
