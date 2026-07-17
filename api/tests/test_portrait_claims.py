from app.store import portrait_claims


def test_portrait_claim_lifecycle_preserves_grounding(migrated_db):
    claim_id = portrait_claims.add(
        claim_type="decision_style",
        text="Seeks evidence before committing to a conclusion.",
        basis="explicit",
        evidence=[{"turn": 3, "quote": "Give me a fair analysis"}],
        source_turn=3,
    )

    active = portrait_claims.active()
    assert active == [{
        "id": claim_id,
        "claim_type": "decision_style",
        "text": "Seeks evidence before committing to a conclusion.",
        "basis": "explicit",
        "evidence": [{"turn": 3, "quote": "Give me a fair analysis"}],
        "status": "active",
        "source_turn": 3,
        "created_at": active[0]["created_at"],
        "updated_at": active[0]["updated_at"],
    }]

    portrait_claims.supersede(claim_id)

    assert portrait_claims.active() == []
    assert portrait_claims.all()[0]["status"] == "superseded"


def test_portrait_claim_exact_duplicate_is_not_added_twice(migrated_db):
    evidence = [{"turn": 1, "quote": "I value autonomy"}]
    first = portrait_claims.add(
        claim_type="value", text="Values autonomy.", basis="explicit",
        evidence=evidence, source_turn=1,
    )
    second = portrait_claims.add(
        claim_type="value", text="  values   AUTONOMY. ", basis="explicit",
        evidence=evidence, source_turn=1,
    )

    assert second == first
    assert len(portrait_claims.active()) == 1


def test_portrait_claims_are_isolated_per_account(tmp_path, monkeypatch):
    from app.data_scope import user_scope
    from app.store import db

    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("VELLUM_AUTH_ENABLED", "1")
    for user_id, text in (("alice", "Alice values depth."), ("bob", "Bob values speed.")):
        with user_scope(user_id):
            db.run_migrations()
            portrait_claims.add(
                claim_type="value", text=text, basis="explicit",
                evidence=[{"turn": 0, "quote": text}], source_turn=0,
            )

    with user_scope("alice"):
        assert [claim["text"] for claim in portrait_claims.active()] == [
            "Alice values depth."
        ]
    with user_scope("bob"):
        assert [claim["text"] for claim in portrait_claims.active()] == [
            "Bob values speed."
        ]
