"""Offline, failure-safe rebuilds of derived personal-model dimensions.

Schwartz can be reconstructed from the canonical message stream: read live user
turns chronologically, stage the complete V2 ledger/projection in memory, then
atomically swap only that dimension.  No cursor is moved and no old projection
is deleted before every structured extraction has succeeded.
"""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime, timezone

from app import config
from app.auth import accounts
from app.config.dimensions_loader import DIMENSION_MAP
from app.data_scope import user_scope
from app.llm.client import is_structured_llm_configured
from app.model_loop import schwartz, traits
from app.model_loop._span import span_text
from app.prompts import runtime
from app.store import db as store_db
from app.store import memory, model


RebuildConflictError = model.TraitRebuildConflictError

_BASIS_RANK = {
    "legacy": 0,
    "emotion": 1,
    "aspiration": 2,
    "self_statement": 3,
    "repeated_behavior": 4,
    "tradeoff": 5,
    "costly_choice": 6,
}


def _positive_batch_turns(batch_turns: int) -> int:
    if (
        isinstance(batch_turns, bool)
        or not isinstance(batch_turns, int)
        or batch_turns < 1
    ):
        raise ValueError("batch_turns must be a positive integer")
    return batch_turns


def preview_schwartz(batch_turns: int) -> dict:
    """Describe exactly which live history a rebuild would read; never call an LLM."""
    batch_turns = _positive_batch_turns(batch_turns)
    last_turn = memory.max_turn()
    if last_turn < 0:
        rows = []
        spans = []
        first_turn = None
        final_turn = None
    else:
        rows = memory.messages_in_turn_range(0, last_turn)
        user_turns = {row["turn"] for row in rows if row["role"] == "user"}
        spans = [
            (start, min(start + batch_turns - 1, last_turn))
            for start in sorted({
                (turn // batch_turns) * batch_turns for turn in user_turns
            })
        ]
        first_turn = 0
        final_turn = last_turn
    return {
        "dimension": "schwartz",
        "first_turn": first_turn,
        "last_turn": final_turn,
        "live_messages": len(rows),
        "user_messages": sum(row["role"] == "user" for row in rows),
        "batch_turns": batch_turns,
        "spans": spans,
    }


def _as_utc(value: str) -> datetime:
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _staged_upsert(staged: dict[tuple[str, str], dict], record: dict) -> None:
    """Apply the same episode-dedup semantics as the durable evidence DAO."""
    key = (record["subdimension"], record["episode_key"])
    current = staged.get(key)
    if current is None:
        staged[key] = dict(record)
        return
    stronger = (
        _BASIS_RANK.get(record["basis"], -1),
        float(record["confidence"]),
        float(record["strength"]),
    ) >= (
        _BASIS_RANK.get(current["basis"], -1),
        float(current["confidence"]),
        float(current["strength"]),
    )
    merged = dict(record if stronger else current)
    starts = [turn for turn in (current.get("start_turn"), record.get("start_turn"))
              if turn is not None]
    ends = [turn for turn in (current.get("end_turn"), record.get("end_turn"))
            if turn is not None]
    merged["start_turn"] = min(starts) if starts else None
    merged["end_turn"] = max(ends) if ends else None
    merged["strength"] = max(float(current["strength"]), float(record["strength"]))
    merged["confidence"] = max(float(current["confidence"]), float(record["confidence"]))
    merged["observed_at"] = max(
        str(current.get("observed_at") or ""), str(record.get("observed_at") or "")
    ) or None
    merged["occurrences"] = 1
    staged[key] = merged


async def rebuild_schwartz(
    batch_turns: int,
    *,
    snapshot: runtime.PromptSnapshot | None = None,
    progress: Callable[[dict], None] | None = None,
) -> dict:
    """Re-extract all live user history and atomically replace Schwartz only."""
    # Fingerprint first. If a message arrives while the plan is being built, the
    # final comparison must reject the run instead of silently treating an older
    # last_turn as the complete corpus.
    guard = model.trait_rebuild_guard("schwartz")
    plan = preview_schwartz(batch_turns)
    if not plan["spans"]:
        raise ValueError("no live user messages are available for Schwartz rebuild")

    staged: dict[tuple[str, str], dict] = {}
    snapshots: list[dict] = []
    current: dict = {}
    selected = snapshot or runtime.default_snapshot()
    dimension = DIMENSION_MAP["schwartz"]

    with runtime.use_snapshot(selected):
        for index, (start_turn, end_turn) in enumerate(plan["spans"], start=1):
            rows = [
                row for row in memory.messages_in_turn_range(start_turn, end_turn)
                if row["role"] == "user"
            ]
            # A soft delete between preview and this read is caught by the final
            # guard. Avoid sending an empty request while preserving old state.
            if not rows:
                continue
            span = span_text(start_turn, end_turn, roles=("user",))
            extracted = await traits._extract(span, "schwartz", dimension, current)
            schwartz.validate_extraction(extracted)
            observed_at = rows[-1]["created_at"]
            records = schwartz.normalize_observations(
                extracted, start_turn=start_turn, end_turn=end_turn,
            )
            for record in records:
                record["observed_at"] = observed_at
                _staged_upsert(staged, record)
            current = schwartz.project(staged.values(), now=_as_utc(observed_at))
            snapshots.append({"content_json": current, "taken_at": observed_at})
            if progress is not None:
                progress({
                    "batch": index,
                    "batches": len(plan["spans"]),
                    "start_turn": start_turn,
                    "end_turn": end_turn,
                    "evidence_episodes": len(staged),
                })

    # The final projection is evaluated at the newest source timestamp. Runtime
    # reads will naturally recompute activation against wall-clock time via API.
    model.replace_trait_projection(
        "schwartz",
        current,
        sample_count=len(snapshots),
        history=snapshots,
        evidence=list(staged.values()),
        expected_guard=guard,
    )
    return {
        **plan,
        "batches": len(snapshots),
        "evidence_episodes": len(staged),
        "assessed_values": sum(
            item.get("priority") is not None for item in current.values()
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.model_loop.rebuild",
        description=(
            "Rebuild a derived trait from canonical SQLite message history. "
            "The default is a read-only preview."
        ),
    )
    parser.add_argument("dimension", choices=["schwartz"])
    parser.add_argument(
        "--batch-turns", type=int, default=config.trait_batch_k(),
        help="global turn width per extraction (default: VELLUM_TRAIT_K)",
    )
    parser.add_argument(
        "--username",
        help="required in family-auth mode; selects exactly one private account",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="perform LLM extraction and atomically replace the selected dimension",
    )
    prompt = parser.add_mutually_exclusive_group()
    prompt.add_argument(
        "--prompt-source", choices=["code", "active"], default="code",
        help="V2 code prompt (default) or the currently published prompt release",
    )
    prompt.add_argument(
        "--prompt-release", type=int, metavar="ID",
        help="use one immutable historical prompt release without activating it",
    )
    return parser


@contextmanager
def _account_scope(username: str | None):
    if config.auth_enabled():
        if not username:
            raise SystemExit("--username is required when VELLUM_AUTH_ENABLED=1")
        user = accounts.get_by_username(username)
        if user is None:
            raise SystemExit(f"unknown account: {username}")
        if user["status"] != "active":
            raise SystemExit(f"account is disabled: {user['username']}")
        with user_scope(user["id"]):
            yield user["username"]
        return
    if username:
        raise SystemExit("--username is only valid when VELLUM_AUTH_ENABLED=1")
    yield "legacy single-user store"


def _selected_snapshot(args) -> tuple[runtime.PromptSnapshot, str]:
    if args.prompt_release is not None:
        if args.prompt_release < 1:
            raise SystemExit("--prompt-release must be a positive release id")
        return (
            runtime.snapshot_for_release(args.prompt_release),
            f"release {args.prompt_release}",
        )
    if args.prompt_source == "active":
        selected = runtime.active_snapshot()
        label = (
            f"active release {selected.release_id}"
            if selected.release_id is not None else "active defaults"
        )
        return selected, label
    return runtime.default_snapshot(), "code-owned Schwartz V2"


def _print_preview(plan: dict, account: str) -> None:
    turns = (
        "none" if plan["first_turn"] is None
        else f"{plan['first_turn']}..{plan['last_turn']}"
    )
    print(f"Account: {account}")
    print(
        f"History: turns {turns}; {plan['live_messages']} live messages; "
        f"{plan['user_messages']} user messages"
    )
    print(
        f"Plan: {len(plan['spans'])} extraction batches "
        f"({plan['batch_turns']} global turns per batch)"
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        _positive_batch_turns(args.batch_turns)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    with _account_scope(args.username) as account:
        if not config.db_path().is_file():
            raise SystemExit(f"personal database not found: {config.db_path()}")
        if args.apply:
            store_db.run_migrations()
        plan = preview_schwartz(args.batch_turns)
        _print_preview(plan, account)
        if not args.apply:
            print(
                "DRY RUN: no LLM calls or database writes were made. "
                "Add --apply to rebuild."
            )
            return 0
        if not plan["spans"]:
            raise SystemExit("no live user messages are available for Schwartz rebuild")
        if not is_structured_llm_configured(stage="trait"):
            raise SystemExit(
                "background modeling LLM is not configured; configure the Admin "
                "background route or export its candidate credentials"
            )
        snapshot, prompt_label = _selected_snapshot(args)
        print(f"Applying with prompt: {prompt_label}")
        print(
            "Maintenance note: keep the chat service stopped until this command "
            "finishes so no in-flight trait job can follow the rebuild."
        )

        def report(event: dict) -> None:
            print(
                f"Batch {event['batch']}/{event['batches']}: "
                f"turns {event['start_turn']}..{event['end_turn']}; "
                f"{event['evidence_episodes']} evidence episodes staged"
            )

        try:
            result = asyncio.run(rebuild_schwartz(
                args.batch_turns,
                snapshot=snapshot,
                progress=report,
            ))
        except RebuildConflictError as exc:
            raise SystemExit(f"rebuild aborted safely: {exc}") from exc
        except Exception as exc:
            raise SystemExit(
                f"rebuild failed before the atomic swap; old Schwartz data was kept: {exc}"
            ) from exc
        print(
            f"Rebuilt Schwartz: {result['batches']} batches, "
            f"{result['evidence_episodes']} distinct episodes, "
            f"{result['assessed_values']}/{len(schwartz.VALUE_KEYS)} values assessed."
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
