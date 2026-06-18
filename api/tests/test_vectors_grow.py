from app.store import vectors


def test_index_grows_past_initial_capacity(monkeypatch):
    """Adding more vectors than the initial capacity must auto-resize, not crash —
    so we can start with a tiny arena (no OOM on small hosts) and grow on demand."""
    monkeypatch.setattr(vectors, "INITIAL_ELEMENTS", 2)
    with vectors.memory_index():
        vs = vectors.VectorStore()
        for i in range(6):  # 6 > initial capacity 2 -> forces grow()
            vs.add(i, [float(i), 1.0, 0.0])
        assert vs.index.get_current_count() == 6
        assert vs.index.get_max_elements() >= 6
        # every vector is still findable after the resizes
        assert len(vs.search([5.0, 1.0, 0.0], k=10)) == 6
