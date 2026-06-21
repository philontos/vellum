"""Routes for browsing past conversation: /history keyset scroll-up (before=)
and the /diary timeline (summary cards + span detail)."""
from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


def test_history_before_returns_older_window(migrated_db):
    from app.store import memory
    for i in range(10):
        memory.append_message("user", f"m{i}")
    r = _client().get("/history", params={"before": 7, "limit": 3})
    assert r.status_code == 200
    assert [m["turn"] for m in r.json()["messages"]] == [4, 5, 6]


def test_history_without_before_is_recent_tail(migrated_db):
    from app.store import memory
    for i in range(5):
        memory.append_message("user", f"m{i}")
    r = _client().get("/history", params={"limit": 2})
    assert r.status_code == 200
    assert [m["turn"] for m in r.json()["messages"]] == [3, 4]


def test_delete_history_hides_turn_from_subsequent_reads(migrated_db):
    from app.store import memory
    for i in range(5):
        memory.append_message("user", f"m{i}")
    client = _client()
    r = client.delete("/history/2")
    assert r.status_code == 200 and r.json() == {"ok": True, "deleted": True}
    turns = [m["turn"] for m in client.get("/history", params={"limit": 10}).json()["messages"]]
    assert turns == [0, 1, 3, 4]


def test_delete_history_is_idempotent(migrated_db):
    from app.store import memory
    memory.append_message("user", "m0")
    client = _client()
    assert client.delete("/history/0").json() == {"ok": True, "deleted": True}
    # second delete is a no-op but still succeeds (idempotent)
    assert client.delete("/history/0").json() == {"ok": True, "deleted": False}


def test_delete_history_unknown_turn_is_ok_noop(migrated_db):
    r = _client().delete("/history/999")
    assert r.status_code == 200 and r.json() == {"ok": True, "deleted": False}


def test_diary_lists_cards_newest_first_and_paginates(migrated_db):
    from app.store import memory
    ids = [memory.add_summary(i, i + 1, f"day {i}") for i in range(5)]
    page1 = _client().get("/diary", params={"limit": 2}).json()["cards"]
    assert [c["id"] for c in page1] == [ids[4], ids[3]]
    assert page1[0]["content"] == "day 4"
    page2 = _client().get("/diary", params={"limit": 2, "before": page1[-1]["id"]}).json()["cards"]
    assert [c["id"] for c in page2] == [ids[2], ids[1]]


def test_diary_detail_returns_summary_and_its_messages(migrated_db):
    from app.store import memory
    for i in range(5):
        memory.append_message("user", f"m{i}")
    sid = memory.add_summary(1, 3, "talked about m1..m3")
    body = _client().get(f"/diary/{sid}").json()
    assert body["summary"]["content"] == "talked about m1..m3"
    assert [m["turn"] for m in body["messages"]] == [1, 2, 3]


def test_diary_detail_404_when_missing(migrated_db):
    r = _client().get("/diary/999")
    assert r.status_code == 404
