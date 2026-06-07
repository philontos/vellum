import pytest

from app.store.vectors import VectorStore


def test_add_and_search_roundtrip(migrated_db):
    store = VectorStore()
    store.add(1, [1.0, 0.0, 0.0])
    store.add(2, [0.0, 1.0, 0.0])
    store.add(3, [0.9, 0.1, 0.0])
    hits = store.search([1.0, 0.0, 0.0], k=2)
    assert hits[0] == 1            # nearest is itself
    assert 3 in hits               # close neighbour beats the orthogonal one


def test_persists_across_instances(migrated_db):
    VectorStore().add(7, [0.2, 0.3, 0.4])
    hits = VectorStore().search([0.2, 0.3, 0.4], k=1)
    assert hits == [7]


def test_empty_search_returns_empty(migrated_db):
    assert VectorStore().search([0.1, 0.2, 0.3], k=5) == []


def test_add_wrong_dim_raises(migrated_db):
    store = VectorStore()
    store.add(1, [1.0, 0.0, 0.0])
    with pytest.raises(RuntimeError):
        store.add(2, [1.0, 0.0])


def test_search_wrong_dim_raises(migrated_db):
    store = VectorStore()
    store.add(1, [1.0, 0.0, 0.0])
    with pytest.raises(ValueError):
        store.search([1.0, 0.0], k=1)
