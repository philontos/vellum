from app.store.vectors import VectorStore


def test_search_scored_returns_label_and_similarity(migrated_db):
    s = VectorStore()
    s.add(1, [1.0, 0.0, 0.0])
    s.add(2, [0.0, 1.0, 0.0])
    hits = s.search_scored([1.0, 0.0, 0.0], k=2)
    assert hits[0][0] == 1
    assert hits[0][1] > 0.99            # near-identical → similarity ~1.0
    # orthogonal vector should score ~0
    by_label = {lbl: sim for lbl, sim in hits}
    assert by_label[2] < 0.5


def test_search_scored_empty(migrated_db):
    assert VectorStore().search_scored([0.1, 0.2, 0.3], k=3) == []
