import pytest

from app.store import memory


def test_append_message_assigns_monotonic_turns(migrated_db):
    a = memory.append_message("user", "hi")
    b = memory.append_message("assistant", "hello")
    c = memory.append_message("user", "how are you")
    assert (a["turn"], b["turn"], c["turn"]) == (0, 1, 2)


def test_streams_partition_tail_and_range_but_share_turn_space(migrated_db):
    memory.append_message("user", "daily one", stream="neutral")        # turn 0
    memory.append_message("user", "counsel one", stream="freud")        # turn 1
    memory.append_message("assistant", "daily two", stream="neutral")   # turn 2
    assert [m["content"] for m in memory.recent_tail(10, stream="neutral")] == ["daily one", "daily two"]
    assert [m["content"] for m in memory.recent_tail(10, stream="freud")] == ["counsel one"]
    # turn is globally monotonic across streams (unique ids), but range reads scope
    assert [m["content"] for m in memory.messages_in_turn_range(0, 2, stream="freud")] == ["counsel one"]
    assert len(memory.messages_in_turn_range(0, 2)) == 3   # stream=None spans all
    assert set(memory.distinct_streams()) == {"neutral", "freud"}
    assert memory.stream_turns_after("neutral", -1) == [0, 2]


def test_summary_cursor_is_per_stream(migrated_db):
    assert memory.get_summary_cursor("freud") == -1            # missing → -1
    memory.advance_summary_cursor("freud", 5)
    assert memory.get_summary_cursor("freud") == 5
    assert memory.get_summary_cursor("neutral") == -1         # independent of freud
    memory.advance_summary_cursor("freud", 9)                 # upsert update
    assert memory.get_summary_cursor("freud") == 9


def test_diary_list_merges_or_scopes_by_stream(migrated_db):
    memory.add_summary(0, 1, "daily card", stream="neutral")
    memory.add_summary(2, 3, "counsel card", stream="freud")
    assert {c["content"] for c in memory.list_summaries(10)} == {"daily card", "counsel card"}
    assert [c["content"] for c in memory.list_summaries(10, stream="freud")] == ["counsel card"]


def test_recent_tail_returns_last_n_in_order(migrated_db):
    for i in range(5):
        memory.append_message("user", f"m{i}")
    tail = memory.recent_tail(limit=3)
    assert [m["content"] for m in tail] == ["m2", "m3", "m4"]


def test_messages_in_turn_range_inclusive(migrated_db):
    for i in range(5):
        memory.append_message("user", f"m{i}")
    rows = memory.messages_in_turn_range(1, 3)
    assert [m["turn"] for m in rows] == [1, 2, 3]


def test_messages_before_returns_window_below_turn_in_order(migrated_db):
    for i in range(10):
        memory.append_message("user", f"m{i}")
    # the 3 messages immediately older than turn 7 -> turns 4,5,6 (oldest->newest)
    rows = memory.messages_before(before_turn=7, limit=3)
    assert [m["turn"] for m in rows] == [4, 5, 6]


def test_messages_before_at_start_returns_empty(migrated_db):
    for i in range(3):
        memory.append_message("user", f"m{i}")
    assert memory.messages_before(before_turn=0, limit=5) == []


def test_list_summaries_newest_first_with_keyset_pagination(migrated_db):
    ids = [memory.add_summary(i, i + 1, f"day {i}") for i in range(5)]
    # newest-first page
    page1 = memory.list_summaries(limit=2)
    assert [s["id"] for s in page1] == [ids[4], ids[3]]
    # next page: everything with id < the last id we saw
    page2 = memory.list_summaries(limit=2, before_id=page1[-1]["id"])
    assert [s["id"] for s in page2] == [ids[2], ids[1]]


def test_summary_add_and_get(migrated_db):
    sid = memory.add_summary(0, 4, "discussed the offer")
    s = memory.get_summary(sid)
    assert s["start_turn"] == 0 and s["end_turn"] == 4
    assert s["content"] == "discussed the offer"


def test_vector_ref_roundtrip(migrated_db):
    label = memory.add_vector_ref("message", 42)
    ref = memory.resolve_vector_ref(label)
    assert ref == {"ref_type": "message", "ref_id": 42}


def test_cursor_get_and_advance(migrated_db):
    assert memory.get_cursor("trait") == -1
    memory.advance_cursor("trait", 9)
    assert memory.get_cursor("trait") == 9


def test_advance_unknown_cursor_raises(migrated_db):
    with pytest.raises(ValueError):
        memory.advance_cursor("nope", 5)


def test_soft_delete_hides_from_recent_tail(migrated_db):
    for i in range(5):
        memory.append_message("user", f"m{i}")
    assert memory.soft_delete(2) is True
    tail = memory.recent_tail(limit=10)
    assert [m["content"] for m in tail] == ["m0", "m1", "m3", "m4"]


def test_soft_delete_hides_from_messages_in_turn_range(migrated_db):
    for i in range(5):
        memory.append_message("user", f"m{i}")
    memory.soft_delete(2)
    rows = memory.messages_in_turn_range(1, 3)
    assert [m["turn"] for m in rows] == [1, 3]


def test_soft_delete_hides_from_messages_before(migrated_db):
    for i in range(10):
        memory.append_message("user", f"m{i}")
    memory.soft_delete(5)
    rows = memory.messages_before(before_turn=7, limit=3)
    # turns 4,5,6 are the window below 7; 5 is deleted so it falls through to 3
    assert [m["turn"] for m in rows] == [3, 4, 6]


def test_soft_delete_hides_from_get_message(migrated_db):
    msg = memory.append_message("user", "secret debug noise")
    assert memory.get_message(msg["id"])["content"] == "secret debug noise"
    memory.soft_delete(msg["turn"])
    assert memory.get_message(msg["id"]) is None


def test_soft_delete_is_idempotent(migrated_db):
    memory.append_message("user", "m0")
    assert memory.soft_delete(0) is True
    assert memory.soft_delete(0) is False  # already gone — no-op


def test_soft_delete_unknown_turn_returns_false(migrated_db):
    assert memory.soft_delete(999) is False


def test_soft_delete_does_not_reuse_turn_numbers(migrated_db):
    memory.append_message("user", "m0")
    memory.append_message("user", "m1")
    memory.soft_delete(1)
    nxt = memory.append_message("user", "m2")
    assert nxt["turn"] == 2  # MAX(turn)+1 still counts the deleted row
