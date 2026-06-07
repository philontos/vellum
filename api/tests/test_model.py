from app.store import model


def test_dossier_get_set(migrated_db):
    assert model.get_dossier() == ""
    model.set_dossier("values autonomy over security")
    assert model.get_dossier() == "values autonomy over security"


def test_trait_upsert_snapshots_history(migrated_db):
    model.set_trait("ocean", {"O": {"score": 71}}, sample_count=1)
    model.set_trait("ocean", {"O": {"score": 78}}, sample_count=2)
    cur = model.get_trait("ocean")
    assert cur["content_json"]["O"]["score"] == 78
    assert cur["sample_count"] == 2
    hist = model.get_trait_history("ocean")
    assert [h["content_json"]["O"]["score"] for h in hist] == [71, 78]


def test_facts_add_list_supersede(migrated_db):
    fid = model.add_fact("allergic to penicillin", source_turn=3)
    assert [f["text"] for f in model.active_facts()] == ["allergic to penicillin"]
    model.supersede_fact(fid)
    assert model.active_facts() == []
