import pytest

from app.chat import retrieval
from app.store import memory
from app.store.vectors import VectorStore


def _seed(monkeypatch):
    # Deterministic 3-dim embeddings keyed by content substring.
    async def fake_embed(text):
        if "offer" in text:
            return [1.0, 0.0, 0.0]
        if "weather" in text:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]
    monkeypatch.setattr(retrieval, "embed", fake_embed)


@pytest.mark.asyncio
async def test_retrieve_hydrates_neighborhood_including_assistant(migrated_db, monkeypatch):
    _seed(monkeypatch)
    # turn 0 user (offer), turn 1 assistant (advice) — only the user turn is embedded
    u = memory.append_message("user", "should I take the offer")
    a = memory.append_message("assistant", "build a financial floor first")
    label = memory.add_vector_ref("message", u["id"])
    VectorStore().add(label, [1.0, 0.0, 0.0])

    snippets = await retrieval.retrieve("thinking about that offer again", k=5)
    text = "\n".join(s["text"] for s in snippets)
    assert "offer" in text and "financial floor" in text   # assistant pulled via linkage


@pytest.mark.asyncio
async def test_recall_message_hit_is_scoped_to_its_stream(migrated_db, monkeypatch):
    _seed(monkeypatch)
    # the same vector lives in the freud stream; querying neutral must not surface it
    u = memory.append_message("user", "should I take the offer", stream="freud")
    memory.append_message("assistant", "build a financial floor", stream="freud")
    VectorStore().add(memory.add_vector_ref("message", u["id"]), [1.0, 0.0, 0.0])

    assert await retrieval.retrieve("that offer again", stream="neutral", k=5) == []
    got = await retrieval.retrieve("that offer again", stream="freud", k=5)
    text = "\n".join(s["text"] for s in got)
    assert "offer" in text and "financial floor" in text


@pytest.mark.asyncio
async def test_recall_summary_hit_scoped_and_hydrates_same_stream(migrated_db, monkeypatch):
    _seed(monkeypatch)
    memory.append_message("user", "should I take the offer", stream="freud")      # 0
    memory.append_message("assistant", "build a financial floor", stream="freud")  # 1
    sid = memory.add_summary(0, 1, "a talk about the offer", stream="freud")
    VectorStore().add(memory.add_vector_ref("summary", sid), [1.0, 0.0, 0.0])

    assert await retrieval.retrieve("offer", stream="neutral", k=5) == []   # summary in another stream
    got = await retrieval.retrieve("offer", stream="freud", k=5)
    text = "\n".join(s["text"] for s in got)
    assert "financial floor" in text   # emits the span's raw same-stream turns, not the digest


@pytest.mark.asyncio
async def test_soft_deleted_anchor_is_not_retrieved(migrated_db, monkeypatch):
    _seed(monkeypatch)
    u = memory.append_message("user", "should I take the offer")
    label = memory.add_vector_ref("message", u["id"])
    VectorStore().add(label, [1.0, 0.0, 0.0])
    memory.soft_delete(u["turn"])  # its vector stays, but the anchor is gone

    snippets = await retrieval.retrieve("thinking about that offer again", k=5)
    assert snippets == []  # resolve -> None -> skipped


@pytest.mark.asyncio
async def test_soft_deleted_neighbour_drops_out_of_window(migrated_db, monkeypatch):
    _seed(monkeypatch)
    u0 = memory.append_message("user", "should I take the offer")     # turn 0
    memory.append_message("assistant", "build a financial floor")     # turn 1
    noise = memory.append_message("user", "debug noise xyz")          # turn 2
    # anchor the only vector on turn 0 (the offer); a wide window spans turn 2
    lbl = memory.add_vector_ref("message", u0["id"])
    VectorStore().add(lbl, [1.0, 0.0, 0.0])
    memory.soft_delete(noise["turn"])

    snippets = await retrieval.retrieve("that offer", k=5, min_sim=0.0, w=2)
    text = "\n".join(s["text"] for s in snippets)
    assert "offer" in text and "financial floor" in text
    assert "debug noise" not in text


@pytest.mark.asyncio
async def test_threshold_gates_irrelevant(migrated_db, monkeypatch):
    _seed(monkeypatch)
    u = memory.append_message("user", "what is the weather")
    label = memory.add_vector_ref("message", u["id"])
    VectorStore().add(label, [0.0, 1.0, 0.0])
    # Query orthogonal to the only stored vector → similarity ~0 → gated out
    snippets = await retrieval.retrieve("unrelated topic xyz", k=5, min_sim=0.35)
    assert snippets == []


@pytest.mark.asyncio
async def test_window_merge_spans_overlapping_turns(migrated_db, monkeypatch):
    """Two user messages in adjacent turns embedded to the same vector;
    querying that vector should produce a single merged snippet covering both."""
    async def fake_embed(text):
        return [1.0, 0.0, 0.0]
    monkeypatch.setattr(retrieval, "embed", fake_embed)

    # seed two user messages at turn 0 and turn 1
    u0 = memory.append_message("user", "first message alpha")
    u1 = memory.append_message("user", "second message beta")
    lbl0 = memory.add_vector_ref("message", u0["id"])
    lbl1 = memory.add_vector_ref("message", u1["id"])
    VectorStore().add(lbl0, [1.0, 0.0, 0.0])
    VectorStore().add(lbl1, [1.0, 0.0, 0.0])

    # w=0 means window = [turn, turn]; turns 0 and 1 are adjacent so they merge
    snippets = await retrieval.retrieve("query", k=5, min_sim=0.0, w=0)
    # Should produce a single merged snippet spanning both turns
    assert len(snippets) == 1
    assert "first message alpha" in snippets[0]["text"]
    assert "second message beta" in snippets[0]["text"]


@pytest.mark.asyncio
async def test_retrieve_explained_surfaces_kept_and_near_miss(migrated_db, monkeypatch):
    """The probe-facing variant keeps per-hit scores and surfaces below-threshold
    near-misses (kept=False) that plain retrieve() silently drops."""
    _seed(monkeypatch)
    # on-topic offer turn (aligned with the "offer" query vector) at turn 0
    u = memory.append_message("user", "should I take the offer")
    VectorStore().add(memory.add_vector_ref("message", u["id"]), [1.0, 0.0, 0.0])
    # off-topic weather turn (orthogonal -> sim ~0 -> below threshold) at turn 1
    wm = memory.append_message("user", "what is the weather")
    VectorStore().add(memory.add_vector_ref("message", wm["id"]), [0.0, 1.0, 0.0])

    out = await retrieval.retrieve_explained(
        "thinking about that offer", k=5, min_sim=0.35, w=0)

    kept = [h for h in out["hits"] if h["kept"]]
    missed = [h for h in out["hits"] if not h["kept"]]
    assert len(kept) == 1 and len(missed) == 1
    assert kept[0]["ref_type"] == "message"
    assert kept[0]["anchor_turn"] == u["turn"]
    assert kept[0]["window"] == [u["turn"], u["turn"]]
    assert kept[0]["sim"] >= 0.35
    assert missed[0]["sim"] < 0.35
    # the near-miss is still informative (resolved ref), just not in the windows
    assert missed[0]["ref_type"] == "message"
    text = "\n".join(s["text"] for s in out["snippets"])
    assert "offer" in text and "weather" not in text


@pytest.mark.asyncio
async def test_explained_message_hit_carries_window_rows_with_anchor(migrated_db, monkeypatch):
    """A kept message hit carries the hydrated neighbourhood it would recall —
    {turn, role, content} rows — with anchor_turn pointing at the matched turn so
    the probe can highlight it among its (un-highlighted) neighbours. No digest."""
    _seed(monkeypatch)
    u = memory.append_message("user", "should I take the offer")          # turn 0 (anchor)
    memory.append_message("assistant", "build a financial floor first")   # turn 1 (neighbour)
    VectorStore().add(memory.add_vector_ref("message", u["id"]), [1.0, 0.0, 0.0])

    out = await retrieval.retrieve_explained("that offer", k=5, min_sim=0.0, w=1)
    hit = next(h for h in out["hits"] if h["kept"])
    assert hit["ref_type"] == "message" and hit["digest"] is None
    assert hit["anchor_turn"] == u["turn"]
    assert [(r["turn"], r["role"]) for r in hit["rows"]] == [(0, "user"), (1, "assistant")]
    anchor_row = next(r for r in hit["rows"] if r["turn"] == hit["anchor_turn"])
    assert "offer" in anchor_row["content"]


@pytest.mark.asyncio
async def test_explained_summary_hit_carries_digest_range_and_rows(migrated_db, monkeypatch):
    """A kept summary hit carries its digest text (otherwise lost), its marked
    turn range as the window, and the real turns it would hydrate. No anchor."""
    async def fake_embed(text):
        return [1.0, 0.0, 0.0]
    monkeypatch.setattr(retrieval, "embed", fake_embed)

    memory.append_message("user", "alpha one")       # turn 0
    memory.append_message("assistant", "beta two")   # turn 1
    sid = memory.add_summary(0, 1, "digest of the span")
    VectorStore().add(memory.add_vector_ref("summary", sid), [1.0, 0.0, 0.0])

    out = await retrieval.retrieve_explained("anything", k=5, min_sim=0.0, w=3)
    hit = next(h for h in out["hits"] if h["kept"])
    assert hit["ref_type"] == "summary"
    assert hit["anchor_turn"] is None
    assert hit["digest"] == "digest of the span"
    assert hit["window"] == [0, 1]
    assert [(r["turn"], r["content"]) for r in hit["rows"]] == [(0, "alpha one"), (1, "beta two")]


@pytest.mark.asyncio
async def test_retrieve_equals_explained_snippets(migrated_db, monkeypatch):
    """retrieve() is just the snippets of retrieve_explained() — same pipeline."""
    _seed(monkeypatch)
    u = memory.append_message("user", "should I take the offer")
    VectorStore().add(memory.add_vector_ref("message", u["id"]), [1.0, 0.0, 0.0])

    snips = await retrieval.retrieve("that offer", k=5, min_sim=0.0, w=1)
    out = await retrieval.retrieve_explained("that offer", k=5, min_sim=0.0, w=1)
    assert snips == out["snippets"]
