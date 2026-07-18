import pytest

from app.inquiry import store
from app.store import db


def _ledger(goal="Decide whether to resign"):
    return {
        "goal": {"text": goal, "evidence": []},
        "observations": [],
        "interpretations": [],
        "hypotheses": [],
        "blocking_unknowns": [],
        "asked_questions": [],
        "provisional_conclusion": None,
    }


def test_inquiry_migration_creates_current_and_history_tables(migrated_db):
    with db.get_conn() as conn:
        names = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert {"inquiries", "inquiry_events"} <= names


def test_open_and_revisioned_update_are_atomic(migrated_db):
    opened = store.open_inquiry(
        stream="neutral",
        opened_turn=4,
        ledger=_ledger(),
        decision={"route": "inquire", "operation": "open"},
        run_id="run-1",
    )

    assert opened["status"] == "exploring"
    assert opened["revision"] == 1
    assert store.get_current("neutral")["id"] == opened["id"]

    updated_ledger = _ledger("Choose whether to leave this job")
    updated = store.apply_revision(
        inquiry_id=opened["id"],
        expected_revision=1,
        status="reviewing",
        ledger=updated_ledger,
        action="synthesize",
        user_turn=6,
        decision={"route": "synthesize", "operation": "update"},
        run_id="run-2",
    )

    assert updated["revision"] == 2
    assert updated["ledger"]["goal"]["text"] == "Choose whether to leave this job"
    events = store.list_events(opened["id"])
    assert [(event["revision_before"], event["revision_after"]) for event in events] == [
        (0, 1), (1, 2),
    ]


def test_stale_revision_never_overwrites_newer_ledger(migrated_db):
    opened = store.open_inquiry(
        stream="neutral", opened_turn=1, ledger=_ledger(), decision={}, run_id="a",
    )
    store.apply_revision(
        inquiry_id=opened["id"], expected_revision=1, status="exploring",
        ledger=_ledger("newer"), action="inquire", user_turn=3,
        decision={}, run_id="b",
    )

    with pytest.raises(store.RevisionConflictError):
        store.apply_revision(
            inquiry_id=opened["id"], expected_revision=1, status="reviewing",
            ledger=_ledger("stale"), action="synthesize", user_turn=5,
            decision={}, run_id="c",
        )

    assert store.get(opened["id"])["ledger"]["goal"]["text"] == "newer"


def test_closed_inquiry_is_immutable_and_a_new_one_links_back(migrated_db):
    first = store.open_inquiry(
        stream="neutral", opened_turn=1, ledger=_ledger(), decision={}, run_id="a",
    )
    closed = store.apply_revision(
        inquiry_id=first["id"], expected_revision=1, status="closed",
        ledger=_ledger(), action="close", user_turn=3, decision={}, run_id="b",
    )

    with pytest.raises(store.ClosedInquiryError):
        store.apply_revision(
            inquiry_id=closed["id"], expected_revision=2, status="exploring",
            ledger=_ledger(), action="resume", user_turn=5, decision={}, run_id="c",
        )

    reopened = store.open_inquiry(
        stream="neutral", opened_turn=5, ledger=_ledger("revisit resignation"),
        decision={}, run_id="d", parent_inquiry_id=closed["id"],
    )
    assert reopened["id"] != closed["id"]
    assert reopened["parent_inquiry_id"] == closed["id"]


def test_only_one_active_inquiry_exists_per_stream(migrated_db):
    store.open_inquiry(
        stream="neutral", opened_turn=1, ledger=_ledger(), decision={}, run_id="a",
    )

    with pytest.raises(store.ActiveInquiryExistsError):
        store.open_inquiry(
            stream="neutral", opened_turn=3, ledger=_ledger("another"),
            decision={}, run_id="b",
        )


def test_paused_inquiry_does_not_block_a_new_topic_and_returns_after_close(
    migrated_db,
):
    first = store.open_inquiry(
        stream="neutral", opened_turn=1, ledger=_ledger("first topic"),
        decision={}, run_id="a",
    )
    paused = store.apply_revision(
        inquiry_id=first["id"], expected_revision=1, status="paused",
        ledger=_ledger("first topic"), action="pause", user_turn=2,
        decision={}, run_id="b",
    )

    second = store.open_inquiry(
        stream="neutral", opened_turn=3, ledger=_ledger("second topic"),
        decision={}, run_id="c",
    )
    assert store.get_current("neutral")["id"] == second["id"]

    store.apply_revision(
        inquiry_id=second["id"], expected_revision=1, status="closed",
        ledger=_ledger("second topic"), action="close", user_turn=4,
        decision={}, run_id="d",
    )

    assert store.get_current("neutral")["id"] == paused["id"]


def test_store_lists_paused_inquiries_separately_from_the_active_one(migrated_db):
    first = store.open_inquiry(
        stream="neutral", opened_turn=1, ledger=_ledger("first topic"),
        decision={}, run_id="a",
    )
    store.apply_revision(
        inquiry_id=first["id"], expected_revision=1, status="paused",
        ledger=_ledger("first topic"), action="pause", user_turn=2,
        decision={}, run_id="b",
    )
    active = store.open_inquiry(
        stream="neutral", opened_turn=3, ledger=_ledger("active topic"),
        decision={}, run_id="c",
    )

    assert store.get_active("neutral")["id"] == active["id"]
    assert [item["id"] for item in store.list_paused("neutral")] == [first["id"]]
