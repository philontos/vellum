from fastapi.testclient import TestClient


def _client():
    from app.main import app
    return TestClient(app)


def test_patch_fact_replaces_active_row_and_preserves_source_turn(migrated_db):
    from app.store import model

    old_id = model.add_fact("old wording", source_turn=12)

    response = _client().patch(
        f"/facts/{old_id}",
        json={"text": "  clearer wording  "},
    )

    assert response.status_code == 200
    edited = response.json()["fact"]
    assert edited["id"] != old_id
    assert edited["text"] == "clearer wording"
    assert edited["source_turn"] == 12
    assert edited["status"] == "active"
    by_id = {fact["id"]: fact for fact in model.all_facts()}
    assert by_id[old_id]["status"] == "superseded"
    assert [fact["id"] for fact in model.active_facts()] == [edited["id"]]


def test_patch_fact_rejects_blank_or_oversized_text_without_writes(migrated_db):
    from app.store import model

    fact_id = model.add_fact("keep me")
    client = _client()

    assert client.patch(f"/facts/{fact_id}", json={"text": "   "}).status_code == 422
    assert client.patch(f"/facts/{fact_id}", json={"text": "x" * 4001}).status_code == 422
    assert [fact["text"] for fact in model.active_facts()] == ["keep me"]
    assert len(model.all_facts()) == 1


def test_patch_fact_rejects_normalized_duplicate_without_writes(migrated_db):
    from app.store import model

    first = model.add_fact("first")
    model.add_fact("Already represented")

    response = _client().patch(
        f"/facts/{first}",
        json={"text": "  already   REPRESENTED  "},
    )

    assert response.status_code == 409
    assert [fact["text"] for fact in model.active_facts()] == [
        "first",
        "Already represented",
    ]
    assert len(model.all_facts()) == 2


def test_patch_fact_returns_404_when_fact_is_not_active(migrated_db):
    from app.store import model

    fact_id = model.add_fact("gone")
    model.supersede_fact(fact_id)

    response = _client().patch(f"/facts/{fact_id}", json={"text": "new"})

    assert response.status_code == 404
    assert model.active_facts() == []


def test_delete_fact_is_idempotent_and_removes_it_from_active_board(migrated_db):
    from app.store import model

    fact_id = model.add_fact("remove me", source_turn=3)
    client = _client()

    first = client.delete(f"/facts/{fact_id}")
    second = client.delete(f"/facts/{fact_id}")

    assert first.status_code == 200
    assert first.json() == {"ok": True, "deleted": True}
    assert second.status_code == 200
    assert second.json() == {"ok": True, "deleted": False}
    assert model.active_facts() == []
    assert model.all_facts()[0]["status"] == "superseded"


def test_fact_mutations_require_login_and_follow_the_authenticated_user(
    tmp_path,
    monkeypatch,
):
    from app.auth import accounts
    from app.data_scope import user_scope
    from app.main import create_app
    from app.store import model

    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    alice = accounts.create_user(
        "alice", "Alice", "correct horse battery staple"
    )
    bob = accounts.create_user(
        "bob", "Bob", "another correct horse battery staple"
    )
    with user_scope(alice["id"]):
        alice_fact = model.add_fact("alice only")
    with user_scope(bob["id"]):
        bob_fact = model.add_fact("bob only")
    assert alice_fact == bob_fact

    anonymous = TestClient(create_app())
    assert anonymous.patch(
        f"/facts/{alice_fact}", json={"text": "intrusion"}
    ).status_code == 401

    alice_client = TestClient(create_app())
    assert alice_client.post(
        "/auth/login",
        json={
            "username": "alice",
            "password": "correct horse battery staple",
        },
    ).status_code == 200
    response = alice_client.patch(
        f"/facts/{alice_fact}", json={"text": "alice edited"}
    )
    assert response.status_code == 200

    with user_scope(alice["id"]):
        assert [fact["text"] for fact in model.active_facts()] == ["alice edited"]
    with user_scope(bob["id"]):
        assert [fact["text"] for fact in model.active_facts()] == ["bob only"]
