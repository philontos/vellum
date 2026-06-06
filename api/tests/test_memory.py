from app.store import memory


def test_append_message_assigns_monotonic_turns(migrated_db):
    a = memory.append_message("user", "hi")
    b = memory.append_message("assistant", "hello")
    c = memory.append_message("user", "how are you")
    assert (a["turn"], b["turn"], c["turn"]) == (0, 1, 2)


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
