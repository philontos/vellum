import pytest

from evals import recall


@pytest.mark.asyncio
async def test_recall_at_k_finds_expected_turn(migrated_db, monkeypatch):
    # deterministic embeddings: "offer/job" -> x axis, everything else -> y axis
    async def fake_embed(text):
        t = text.lower()
        return [1.0, 0.0] if ("offer" in t or "job" in t) else [0.0, 1.0]
    monkeypatch.setattr(recall.ingest, "embed", fake_embed)
    monkeypatch.setattr(recall.retrieval, "embed", fake_embed)

    case = {
        "corpus": [
            {"role": "user", "content": "I got a startup offer"},
            {"role": "user", "content": "the weather is grey"},
        ],
        "query": "about that job offer", "expect_turns": [0],
    }
    score = await recall.run_case(case, k=3, min_sim=0.3)
    assert score["hit"] is True and score["recall"] == 1.0
