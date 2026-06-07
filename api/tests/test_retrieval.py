from app.chat import retrieval
from app.store import memory
from app.store.vectors import VectorStore


def _seed(monkeypatch):
    # Deterministic 3-dim embeddings keyed by content substring.
    def fake_embed_sync(text):
        if "offer" in text:
            return [1.0, 0.0, 0.0]
        if "weather" in text:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]
    monkeypatch.setattr(retrieval, "_embed_sync", fake_embed_sync)


def test_retrieve_hydrates_neighborhood_including_assistant(migrated_db, monkeypatch):
    _seed(monkeypatch)
    # turn 0 user (offer), turn 1 assistant (advice) — only the user turn is embedded
    u = memory.append_message("user", "should I take the offer")
    a = memory.append_message("assistant", "build a financial floor first")
    label = memory.add_vector_ref("message", u["id"])
    VectorStore().add(label, retrieval._embed_sync("should I take the offer"))

    snippets = retrieval.retrieve("thinking about that offer again", k=5)
    text = "\n".join(s["text"] for s in snippets)
    assert "offer" in text and "financial floor" in text   # assistant pulled via linkage


def test_threshold_gates_irrelevant(migrated_db, monkeypatch):
    _seed(monkeypatch)
    u = memory.append_message("user", "what is the weather")
    label = memory.add_vector_ref("message", u["id"])
    VectorStore().add(label, retrieval._embed_sync("what is the weather"))
    # Query orthogonal to the only stored vector → similarity ~0 → gated out
    snippets = retrieval.retrieve("unrelated topic xyz", k=5, min_sim=0.35)
    assert snippets == []
