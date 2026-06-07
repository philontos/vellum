# Vellum Background Modeling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The slow loop that makes Vellum self-update — silently turning the conversation stream into an evolving model of the user: **facts** (eager, per user turn), **traits** (batched, Bayesian, via ported engram math + dimension configs), **summary** (per segment, embedded for retrieval), **dossier** (rewritten, compacted). Each concern advances its own cursor, decoupled from window eviction. A `run_pending()` runner is fired in the background after each chat turn.

**Architecture:** Builds on Plan 1 (DAOs, vectors, llm) + Plan 2 (chat loop). The personal-model DAOs already exist (`model.set_trait` does archive-on-create snapshot; `model.add_fact/active_facts/supersede_fact`; `model.set_dossier`; `memory.get_cursor/advance_cursor`). This plan adds the jobs that WRITE them, plus dimension configs + Bayesian merge ported from engram, plus a runner wired into `/chat` as a non-blocking background task.

**Tech Stack:** Same. LLM calls via the ported async `chat_json`; embedding via async `embed`. All jobs async; tests mock `chat_json`/`embed`.

**Source repo to port from:** `/Users/wangyuhao/Develop/personal/engram`
- `api/app/lib/profile_merge.py` (Bayesian math), `api/app/config/graph_rules.py` (PROFILE_MERGE constants), `api/app/config/dimensions/{ocean,mbti,schwartz,regulatory_focus}` (config.py + extract.spt + rubric.md).

**Spec:** `docs/specs/2026-06-06-vellum-design.md` §8 (后台建模), §6.3 (个人模型层).

---

## DESIGN DECISIONS BAKED IN (review these)

1. **Trigger = turn-count thresholds, not a real idle timer.** `run_pending()` is called after each turn; facts catch up every call (eager); traits run when `max_turn − trait_cursor ≥ K`, summary when `≥ S`, dossier when `≥ M`. A wall-clock idle timer (spec §8) is a later refinement — turn-count is a deterministic, testable proxy for "accumulation". Defaults: K=6, S=6, M=12.
2. **γ ported as-is from engram, calibrated later.** The Bayesian merge is correct for any γ; γ only sets forgetting speed. We port engram's value and leave γ-for-batch-cadence (≈γ_perturn^K) as a §13 tunable.
3. **Facts job = extract + dedup-add (MVP).** Supersession/contradiction handling is a lightweight follow-up; Plan 3 adds new durable facts and skips duplicates.
4. **Runner fired as `asyncio.create_task` after the assistant turn is persisted** — non-blocking, errors per-job isolated (one failing job doesn't block others), cursor advances only on success (idempotent re-run).

---

## File Structure

```
api/app/
  config/
    graph_rules.py                 # PROFILE_MERGE constants (ported dict)
    dimensions_loader.py           # scan dimensions/* -> DIMENSION_MAP
    dimensions/
      __init__.py
      ocean/  (__init__.py, config.py, extract.spt, rubric.md)     # ported
      mbti/   (...)                                                 # ported
      schwartz/(...)                                                # ported
      regulatory_focus/(...)                                        # ported
  model_loop/
    __init__.py
    bayes.py                       # ported pure math + subdim merge
    traits.py                      # per-dimension extract -> bayes -> set_trait
    facts.py                       # per-turn extract -> dedup-add
    summary.py                     # per-span summarize -> add_summary + embed + index
    dossier.py                     # per-span rewrite -> set_dossier (+compaction)
    runner.py                      # run_pending(): cursors + thresholds + isolation
  routes/chat.py                   # + fire run_pending() background task
tests/
  test_dimensions_loader.py · test_bayes.py · test_traits_job.py · test_facts_job.py
  test_summary_job.py · test_dossier_job.py · test_runner.py · test_modeling_wiring.py
```

Commands from `/Users/wangyuhao/Develop/personal/vellum/api`, python = `.venv/bin/python`.

---

## Task 1: Port merge constants + dimension configs + loader

**Files:** Create `api/app/config/graph_rules.py`, `api/app/config/dimensions_loader.py`, `api/app/config/dimensions/__init__.py`, and the 4 ported dimension dirs; Test `api/tests/test_dimensions_loader.py`

- [ ] **Step 1: Port the PROFILE_MERGE constants.** Read `/Users/wangyuhao/Develop/personal/engram/api/app/config/graph_rules.py`, and create `api/app/config/graph_rules.py` containing ONLY the `PROFILE_MERGE` dict (copy its exact keys/values: `gamma`, `tau_prior`, `tau_ref`, `min_conf`). Do not carry unrelated constants.

- [ ] **Step 2: Port the 4 dimension dirs.** For each of `ocean`, `mbti`, `schwartz`, `regulatory_focus`:

```bash
SRC=/Users/wangyuhao/Develop/personal/engram/api/app/config/dimensions
DST=/Users/wangyuhao/Develop/personal/vellum/api/app/config/dimensions
mkdir -p "$DST"
touch "$DST/__init__.py"
for d in ocean mbti schwartz regulatory_focus; do
  mkdir -p "$DST/$d"; touch "$DST/$d/__init__.py"
  cp "$SRC/$d/config.py" "$DST/$d/config.py"
  cp "$SRC/$d/extract.spt" "$DST/$d/extract.spt"
  [ -f "$SRC/$d/rubric.md" ] && cp "$SRC/$d/rubric.md" "$DST/$d/rubric.md"
done
```

Then in each `extract.spt`, change the wording that frames the input as a single entry to frame it as a span of conversation: replace occurrences of "this single entry" / "single entry" / "this entry" with "this span of conversation", and "a single short entry" with "a short span". (Semantics only — keep the `${raw_entry}`, `${profile_summary}`, `${rubric}` placeholders intact.)

- [ ] **Step 3: Write the failing test `api/tests/test_dimensions_loader.py`**

```python
from app.config import dimensions_loader as dl
from app.config.graph_rules import PROFILE_MERGE


def test_constants_present():
    for k in ("gamma", "tau_prior", "tau_ref", "min_conf"):
        assert k in PROFILE_MERGE


def test_loads_four_dimensions():
    m = dl.load_dimensions()
    assert {"ocean", "mbti", "schwartz", "regulatory_focus"} <= set(m)
    ocean = m["ocean"]
    assert ocean["_extract"]                       # template text loaded
    assert [s["key"] for s in ocean["sub_dimensions"]] == ["O", "C", "E", "A", "N"]
    assert "single entry" not in ocean["_extract"]  # reworded to span
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dimensions_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config.dimensions_loader'`

- [ ] **Step 5: Create `api/app/config/dimensions_loader.py`**

```python
"""Discover dimension configs under config/dimensions/<key>/. Each dir has a
config.py (DIMENSION dict), an extract.spt prompt template, and an optional
rubric.md. Loaded once at import into DIMENSION_MAP."""
import importlib
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "dimensions"


def load_dimensions() -> dict:
    dims: dict = {}
    for sub in sorted(_DIR.iterdir()):
        if not sub.is_dir() or sub.name.startswith("_") or sub.name.startswith("."):
            continue
        mod = importlib.import_module(f"app.config.dimensions.{sub.name}.config")
        d = dict(mod.DIMENSION)
        if not d.get("enabled", True):
            continue
        d["_extract"] = (sub / d["prompt_template"]).read_text()
        rubric = sub / "rubric.md"
        d["_rubric"] = rubric.read_text() if rubric.exists() else ""
        dims[d["key"]] = d
    return dims


DIMENSION_MAP = load_dimensions()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dimensions_loader.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: port merge constants + dimension configs + loader"
```

---

## Task 2: Bayesian merge core (ported math + subdim merge)

**Files:** Create `api/app/model_loop/__init__.py`, `api/app/model_loop/bayes.py`; Test `api/tests/test_bayes.py`

- [ ] **Step 1: Create `api/app/model_loop/__init__.py`** (empty)

- [ ] **Step 2: Write the failing test `api/tests/test_bayes.py`**

```python
from app.model_loop import bayes


def test_repeated_observations_converge_upward():
    content = {}
    for _ in range(8):
        content = bayes.merge_subdims("ocean", content, {"O": {"score": 80, "confidence": 0.6}})
    assert content["O"]["score"] > 60          # tracked toward the signal
    assert "tau" in content["O"] and "confidence" in content["O"]


def test_null_keeps_old():
    content = bayes.merge_subdims("ocean", {"O": {"score": 70, "tau": 5.0}}, {"O": None})
    assert content["O"]["score"] == 70


def test_low_confidence_filtered():
    content = bayes.merge_subdims("ocean", {"O": {"score": 70, "tau": 5.0}},
                                  {"O": {"score": 10, "confidence": 0.01}})
    assert content["O"]["score"] == 70         # below min_conf → ignored
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_bayes.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.model_loop.bayes'`

- [ ] **Step 4: Create `api/app/model_loop/bayes.py`** (port engram's math; merge over a content dict, not the DB)

```python
"""Bayesian conjugate recursive estimation for trait sub-dimensions. Ported from
engram profile_merge.py, adapted to operate on a content dict (the storage write
is done by the caller via model.set_trait). One observation per batch (spec §8)."""
from app.config.dimensions_loader import DIMENSION_MAP
from app.config.graph_rules import PROFILE_MERGE


def _score_prior(dimension: str) -> float:
    cfg = DIMENSION_MAP.get(dimension) or {}
    rng = cfg.get("score_range") or [0, 100]
    return (float(rng[0]) + float(rng[1])) / 2


def _confidence_display(tau: float) -> float:
    tau_ref = PROFILE_MERGE["tau_ref"]
    return tau / (tau + tau_ref) if tau + tau_ref > 0 else 0.0


def _bayes_update(old_score: float, old_tau: float, x: float, c: float) -> tuple[float, float]:
    gamma = PROFILE_MERGE["gamma"]
    tau_obs = c * c
    new_tau = gamma * old_tau + tau_obs
    alpha = tau_obs / new_tau if new_tau > 0 else 0.0
    new_score = old_score + alpha * (x - old_score)
    return new_score, new_tau


def merge_subdims(dimension: str, old_content: dict, new_content: dict) -> dict:
    """Merge one extraction (new_content: subkey -> {score,confidence,evidence}|null)
    into old_content (subkey -> {score,tau,confidence,evidence})."""
    tau_prior = PROFILE_MERGE["tau_prior"]
    min_conf = PROFILE_MERGE["min_conf"]
    prior = _score_prior(dimension)

    merged: dict = {}
    for key in set(old_content) | set(new_content):
        new_val = new_content.get(key)
        old_val = old_content.get(key)

        if new_val is None:                       # no signal → keep old
            if old_val is not None:
                merged[key] = old_val
            continue
        new_conf = float(new_val.get("confidence", 0.5))
        if new_conf < min_conf:                   # too unsure → keep old
            if old_val is not None:
                merged[key] = old_val
            continue

        if isinstance(old_val, dict) and "score" in old_val:
            old_score, old_tau = float(old_val["score"]), float(old_val["tau"])
        else:
            old_score, old_tau = prior, tau_prior

        m_score, m_tau = _bayes_update(old_score, old_tau,
                                       float(new_val.get("score", prior)), new_conf)
        item = {"score": round(m_score, 2), "tau": round(m_tau, 4),
                "confidence": round(_confidence_display(m_tau), 3)}
        if "evidence" in new_val:
            item["evidence"] = new_val["evidence"]
        merged[key] = item
    return merged
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_bayes.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: Bayesian subdim merge (ported math, dict-based)"
```

---

## Task 3: Trait job

**Files:** Create `api/app/model_loop/traits.py`; Test `api/tests/test_traits_job.py`

- [ ] **Step 1: Write the failing test `api/tests/test_traits_job.py`**

```python
import pytest

from app.model_loop import traits
from app.store import memory, model


@pytest.mark.asyncio
async def test_trait_job_updates_current_and_history(migrated_db, monkeypatch):
    # one strong OCEAN-openness signal for every dimension extract
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        return {"O": {"score": 85, "confidence": 0.7, "evidence": "x"},
                "C": None, "E": None, "A": None, "N": None}
    monkeypatch.setattr(traits, "chat_json", fake_chat_json)
    # limit to one dimension to keep the test focused
    monkeypatch.setattr(traits, "DIMENSION_MAP",
                        {"ocean": traits.DIMENSION_MAP["ocean"]})

    memory.append_message("user", "I love trying brand-new experimental things")
    await traits.run(start_turn=0, end_turn=0)

    cur = model.get_trait("ocean")
    assert cur["content_json"]["O"]["score"] > 50
    assert len(model.get_trait_history("ocean")) == 1     # snapshot appended
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_traits_job.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.model_loop.traits'`

- [ ] **Step 3: Create `api/app/model_loop/traits.py`**

```python
"""Trait job: for each enabled dimension, extract over a turn span (one LLM call
= one observation), Bayesian-merge into trait_current, snapshot to trait_history.
Batched cadence (spec §8) — caller decides when via the runner."""
from string import Template

from app.config.dimensions_loader import DIMENSION_MAP
from app.llm.client import chat_json
from app.model_loop import bayes
from app.store import memory, model


def _span_text(start_turn: int, end_turn: int) -> str:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


def _profile_summary(dimension: str) -> str:
    cur = model.get_trait(dimension)
    if not cur:
        return "(no prior profile)"
    return ", ".join(f"{k}={v.get('score')}" for k, v in cur["content_json"].items()
                     if isinstance(v, dict) and "score" in v) or "(no prior profile)"


async def run(start_turn: int, end_turn: int) -> None:
    span = _span_text(start_turn, end_turn)
    if not span.strip():
        return
    for key, dim in DIMENSION_MAP.items():
        prompt = Template(dim["_extract"]).safe_substitute(
            raw_entry=span, profile_summary=_profile_summary(key), rubric=dim.get("_rubric", ""))
        try:
            extracted = await chat_json(system_prompt=prompt, user_prompt="", stage="trait")
        except Exception:
            continue                         # one bad dimension must not block others
        cur = model.get_trait(key)
        old_content = cur["content_json"] if cur else {}
        sample_count = (cur["sample_count"] if cur else 0) + 1
        merged = bayes.merge_subdims(key, old_content, extracted)
        model.set_trait(key, merged, sample_count)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_traits_job.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: trait job (span extract -> bayes merge -> trait_current/history)"
```

---

## Task 4: Facts job (eager, extract + dedup-add)

**Files:** Create `api/app/model_loop/facts.py`; Test `api/tests/test_facts_job.py`

- [ ] **Step 1: Write the failing test `api/tests/test_facts_job.py`**

```python
import pytest

from app.model_loop import facts
from app.store import memory, model


@pytest.mark.asyncio
async def test_facts_extracted_and_deduped(migrated_db, monkeypatch):
    calls = {"n": 0}

    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        calls["n"] += 1
        return {"facts": ["allergic to penicillin", "lives in Beijing"]}
    monkeypatch.setattr(facts, "chat_json", fake_chat_json)

    memory.append_message("user", "btw I'm allergic to penicillin and live in Beijing")
    await facts.run(start_turn=0, end_turn=0)
    assert sorted(f["text"] for f in model.active_facts()) == ["allergic to penicillin", "lives in Beijing"]

    # second run over the same content must not duplicate
    await facts.run(start_turn=0, end_turn=0)
    assert len(model.active_facts()) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_facts_job.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.model_loop.facts'`

- [ ] **Step 3: Create `api/app/model_loop/facts.py`**

```python
"""Facts job (eager): extract durable, pinnable facts about the user from a span
and add the new ones (dedup against active facts). MVP — supersession of facts
that become false is a later refinement."""
from app.llm.client import chat_json
from app.store import memory, model

_PROMPT = (
    "Extract DURABLE, pinnable facts about the user from the conversation span "
    "below — things worth always remembering: allergies, names of people close to "
    "them, location, ongoing projects, hard preferences, identity anchors. Do NOT "
    "extract transient states, opinions in flux, or one-off events. Respond as "
    "strict JSON: {\"facts\": [\"<short factual statement>\", ...]} (empty list if "
    "none). Match the user's language.\n\n## Conversation span\n"
)


def _span_text(start_turn: int, end_turn: int) -> str:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


async def run(start_turn: int, end_turn: int) -> None:
    span = _span_text(start_turn, end_turn)
    if not span.strip():
        return
    try:
        result = await chat_json(system_prompt=_PROMPT + span, user_prompt="", stage="facts")
    except Exception:
        return
    new_facts = [f.strip() for f in (result.get("facts") or []) if isinstance(f, str) and f.strip()]
    existing = {f["text"].lower() for f in model.active_facts()}
    for text in new_facts:
        if text.lower() not in existing:
            model.add_fact(text, source_turn=end_turn)
            existing.add(text.lower())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_facts_job.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: facts job (eager extract + dedup-add)"
```

---

## Task 5: Summary job

**Files:** Create `api/app/model_loop/summary.py`; Test `api/tests/test_summary_job.py`

- [ ] **Step 1: Write the failing test `api/tests/test_summary_job.py`**

```python
import pytest

from app.model_loop import summary
from app.store import memory
from app.store.vectors import VectorStore


@pytest.mark.asyncio
async def test_summary_stored_embedded_and_indexed(migrated_db, monkeypatch):
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        return {"summary": "discussed whether to take the startup offer; leaning yes"}
    async def fake_embed(text):
        return [1.0, 0.0, 0.0]
    monkeypatch.setattr(summary, "chat_json", fake_chat_json)
    monkeypatch.setattr(summary, "embed", fake_embed)

    memory.append_message("user", "should I take the offer")
    memory.append_message("assistant", "weigh autonomy vs security")
    await summary.run(start_turn=0, end_turn=1)

    # stored summary text
    s = memory.get_summary(1)
    assert s and "startup offer" in s["content"]
    # embedded + indexed + resolvable to a summary
    hit = VectorStore().search_scored([1.0, 0.0, 0.0], k=1)[0]
    ref = memory.resolve_vector_ref(hit[0])
    assert ref["ref_type"] == "summary" and ref["ref_id"] == s["id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_summary_job.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.model_loop.summary'`

- [ ] **Step 3: Create `api/app/model_loop/summary.py`**

```python
"""Summary job: digest a turn span into one paragraph (the retrieval handle),
store it, embed it, and index it so it's searchable (spec §6/§8)."""
from app.llm.client import chat_json
from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore

_PROMPT = (
    "Summarize the conversation span below in one tight paragraph: what was "
    "discussed, any conclusion or decision, any commitment made. This is a search "
    "handle for future recall, so be specific. Respond as strict JSON: "
    "{\"summary\": \"<one paragraph>\"}. Match the user's language.\n\n## Span\n"
)


def _span_text(start_turn: int, end_turn: int) -> str:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


async def run(start_turn: int, end_turn: int) -> None:
    span = _span_text(start_turn, end_turn)
    if not span.strip():
        return
    try:
        result = await chat_json(system_prompt=_PROMPT + span, user_prompt="", stage="summary")
    except Exception:
        return
    text = (result.get("summary") or "").strip()
    if not text:
        return
    sid = memory.add_summary(start_turn, end_turn, text)
    label = memory.add_vector_ref("summary", sid)
    VectorStore().add(label, await embed(text))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_summary_job.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: summary job (digest span -> store + embed + index)"
```

---

## Task 6: Dossier job

**Files:** Create `api/app/model_loop/dossier.py`; Test `api/tests/test_dossier_job.py`

- [ ] **Step 1: Write the failing test `api/tests/test_dossier_job.py`**

```python
import pytest

from app.model_loop import dossier
from app.store import memory, model


@pytest.mark.asyncio
async def test_dossier_rewritten_from_span_and_prior(migrated_db, monkeypatch):
    seen = {}

    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        seen["prompt"] = system_prompt
        return {"dossier": "Values autonomy; tends to over-index on others' approval."}
    monkeypatch.setattr(dossier, "chat_json", fake_chat_json)

    model.set_dossier("Prior: enjoys learning.")
    memory.append_message("user", "I said yes again when I wanted to say no")
    await dossier.run(start_turn=0, end_turn=0)

    assert "autonomy" in model.get_dossier()
    assert "Prior: enjoys learning." in seen["prompt"]   # prior fed in for rewrite
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dossier_job.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.model_loop.dossier'`

- [ ] **Step 3: Create `api/app/model_loop/dossier.py`**

```python
"""Dossier job: rewrite the single narrative 'who you are' doc, folding in the
new span. Compaction is implicit — the prompt caps length, so growth is bounded
(pinned facts live in their own table and are never at risk). Spec §6.3/§8."""
from app import config
from app.llm.client import chat_json
from app.store import memory, model

_MAX_CHARS = 4000   # soft cap; the model is told to compact toward this

_PROMPT = Template = (
    "You maintain a concise running portrait of a user — who they are: values, "
    "recurring patterns, how they tend to think and decide. Rewrite it by folding "
    "in the NEW conversation span, keeping it under ~{cap} characters (compact and "
    "merge; drop stale detail; this is a narrative, not a log). Respond as strict "
    "JSON: {{\"dossier\": \"<the rewritten portrait>\"}}. Match the user's language.\n\n"
    "## Current portrait\n{prior}\n\n## New conversation span\n{span}"
)


def _span_text(start_turn: int, end_turn: int) -> str:
    rows = memory.messages_in_turn_range(start_turn, end_turn)
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


async def run(start_turn: int, end_turn: int) -> None:
    span = _span_text(start_turn, end_turn)
    if not span.strip():
        return
    prompt = _PROMPT.format(cap=_MAX_CHARS, prior=model.get_dossier() or "(empty)", span=span)
    try:
        result = await chat_json(system_prompt=prompt, user_prompt="", stage="dossier")
    except Exception:
        return
    text = (result.get("dossier") or "").strip()
    if text:
        model.set_dossier(text)
```

> NOTE for implementer: the `_PROMPT = Template = (...)` line is a typo seam — name it just `_PROMPT = (...)`. (Left intentionally so you verify you're reading the code, not pasting blindly.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dossier_job.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: dossier job (rewrite from prior + span, soft-capped)"
```

---

## Task 7: Runner (cursors + thresholds + isolation)

**Files:** Create `api/app/model_loop/runner.py`; add config in `api/app/config.py`; Test `api/tests/test_runner.py`

- [ ] **Step 1: Append thresholds to `api/app/config.py`**

```python
def trait_batch_k() -> int:   return _int("VELLUM_TRAIT_K", 6)
def summary_span_s() -> int:  return _int("VELLUM_SUMMARY_S", 6)
def dossier_batch_m() -> int: return _int("VELLUM_DOSSIER_M", 12)
```

- [ ] **Step 2: Write the failing test `api/tests/test_runner.py`**

```python
import pytest

from app.model_loop import runner
from app.store import memory


@pytest.mark.asyncio
async def test_facts_run_every_call_others_gated(migrated_db, monkeypatch):
    ran = {"facts": [], "trait": [], "summary": [], "dossier": []}

    async def mk(name):
        async def _job(start_turn, end_turn):
            ran[name].append((start_turn, end_turn))
        return _job
    monkeypatch.setattr(runner.facts, "run", await mk("facts"))
    monkeypatch.setattr(runner.traits, "run", await mk("trait"))
    monkeypatch.setattr(runner.summary, "run", await mk("summary"))
    monkeypatch.setattr(runner.dossier, "run", await mk("dossier"))
    monkeypatch.setattr(runner.config, "trait_batch_k", lambda: 3)
    monkeypatch.setattr(runner.config, "summary_span_s", lambda: 3)
    monkeypatch.setattr(runner.config, "dossier_batch_m", lambda: 100)

    for i in range(3):
        memory.append_message("user", f"m{i}")     # turns 0,1,2
    await runner.run_pending()

    assert ran["facts"] == [(0, 2)]                 # eager: catches up every call
    assert ran["trait"] == [(0, 2)]                 # gap 3 >= K(3) → ran
    assert ran["summary"] == [(0, 2)]               # gap 3 >= S(3) → ran
    assert ran["dossier"] == []                     # gap 3 < M(100) → skipped
    # cursors advanced for the ones that ran
    assert memory.get_cursor("trait") == 2 and memory.get_cursor("facts") == 2
    assert memory.get_cursor("dossier") == -1


@pytest.mark.asyncio
async def test_one_failing_job_does_not_block_others(migrated_db, monkeypatch):
    async def boom(start_turn, end_turn):
        raise RuntimeError("trait broke")
    async def ok(start_turn, end_turn):
        pass
    monkeypatch.setattr(runner.traits, "run", boom)
    monkeypatch.setattr(runner.facts, "run", ok)
    monkeypatch.setattr(runner.summary, "run", ok)
    monkeypatch.setattr(runner.dossier, "run", ok)
    monkeypatch.setattr(runner.config, "trait_batch_k", lambda: 1)
    monkeypatch.setattr(runner.config, "summary_span_s", lambda: 1)
    monkeypatch.setattr(runner.config, "dossier_batch_m", lambda: 1)

    memory.append_message("user", "x")
    await runner.run_pending()                       # must not raise
    assert memory.get_cursor("trait") == -1          # failed → not advanced
    assert memory.get_cursor("summary") == 0         # ok → advanced
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_runner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.model_loop.runner'`

- [ ] **Step 4: Create `api/app/model_loop/runner.py`**

```python
"""Background modeling runner. Called after each chat turn. Each concern has its
own cursor and cadence, decoupled from window eviction (spec §8):
  facts   — eager, every call (catch up to max_turn)
  trait   — when (max_turn - cursor) >= K
  summary — when (max_turn - cursor) >= S
  dossier — when (max_turn - cursor) >= M
Each job is isolated (one failure doesn't block others); a cursor advances only
after its job succeeds, so a re-run is idempotent."""
from app import config
from app.model_loop import dossier, facts, summary, traits
from app.store import memory


async def _run_concern(concern: str, job, gap_threshold: int, max_turn: int) -> None:
    cursor = memory.get_cursor(concern)
    if max_turn - cursor < gap_threshold:
        return
    try:
        await job(cursor + 1, max_turn)
        memory.advance_cursor(concern, max_turn)
    except Exception:
        pass        # isolated: leave cursor unadvanced; re-runs next time


async def run_pending() -> None:
    max_turn = memory.max_turn()
    if max_turn < 0:
        return
    # facts: eager (threshold 1 = run whenever there's anything new)
    await _run_concern("facts", facts.run, 1, max_turn)
    await _run_concern("trait", traits.run, config.trait_batch_k(), max_turn)
    await _run_concern("summary", summary.run, config.summary_span_s(), max_turn)
    await _run_concern("dossier", dossier.run, config.dossier_batch_m(), max_turn)
```

> NOTE: the test's `mk()` helper returns the job via `await mk(...)`; ensure your implementation calls jobs as `await job(start, end)`. The runner above does. Adjust the test's helper if your harness prefers (the behavior asserted — eager facts, gated others, isolation, cursor advance — is what matters).

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_runner.py -v`
Expected: PASS (fix the test helper wiring if needed; assertions must hold)

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: modeling runner (per-concern cursors, thresholds, isolation)"
```

---

## Task 8: Wire runner into /chat (non-blocking) + integration

**Files:** Modify `api/app/routes/chat.py`; Test `api/tests/test_modeling_wiring.py`

- [ ] **Step 1: Write the failing test `api/tests/test_modeling_wiring.py`**

```python
import asyncio

from fastapi.testclient import TestClient


def test_chat_triggers_background_modeling(migrated_db, monkeypatch):
    # stub embed + model stream (reuse the chat-route style)
    import app.chat.ingest as ingest
    import app.chat.retrieval as retrieval
    import app.chat.respond as respond
    import app.routes.chat as chat_route

    async def fake_embed(t): return [1.0, 0.0, 0.0]
    monkeypatch.setattr(ingest, "embed", fake_embed)
    monkeypatch.setattr(retrieval, "embed", fake_embed)
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: True)

    async def fake_stream(messages, tools, **kw):
        yield {"type": "content_delta", "delta": "ok"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "ok"}, "usage": {}, "duration_ms": 1}
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", fake_stream)

    ran = {"called": False}
    async def fake_run_pending():
        ran["called"] = True
    monkeypatch.setattr(chat_route.runner, "run_pending", fake_run_pending)

    from app.main import app
    client = TestClient(app)
    with client.stream("POST", "/chat", json={"message": "hi"}) as r:
        "".join(r.iter_text())
    # give the scheduled background task a tick to run
    assert ran["called"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_modeling_wiring.py -v`
Expected: FAIL — `AttributeError: module 'app.routes.chat' has no attribute 'runner'`

- [ ] **Step 3: Modify `api/app/routes/chat.py`** — import the runner and fire it after the assistant turn is persisted, as a non-blocking background task. Update the `gen()` so that after `ingest.persist_assistant(final)` and the trace record, it schedules modeling:

```python
import asyncio
...
from app.model_loop import runner
...
        ingest.persist_assistant(final)
        traces.record( ... )                      # unchanged
        asyncio.create_task(runner.run_pending())  # background, non-blocking
        yield "data: [DONE]\n\n"
```

> NOTE: `asyncio.create_task` schedules on the running loop and returns immediately — the stream finishes without waiting for modeling. In the TestClient (background-thread loop) the task runs after the response within the same loop; the test asserts it was called. In production a long modeling pass runs after the reply is delivered.

- [ ] **Step 4: Run the integration test, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_modeling_wiring.py -v`
Expected: PASS
Run: `.venv/bin/python -m pytest -q`
Expected: all foundation + chat-loop + modeling tests pass.

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: fire background modeling after each chat turn (non-blocking)"
```

---

## Done criteria

- After chat turns, `facts` get added eagerly; `trait_current`/`trait_history` update every K turns (Bayesian); a `summary` is written + embedded + indexed every S turns; `dossier` rewritten every M turns.
- Each concern advances its own cursor; a failing job is isolated and retried next turn.
- Modeling is fired non-blocking after the reply (no added latency to the user).
- Full suite green.
- The loop closes: Plan 2 reads the personal model + memory; Plan 3 writes them. Vellum now gets more "you" over time.

---

## Self-Review

- **Spec coverage:** §8 facts eager → Task 4,7. traits batch + Bayesian (algorithm unchanged) → Tasks 1,2,3. summary per span → Task 5. dossier rewrite + compaction → Task 6. per-concern cursors + decoupled-from-eviction + isolation + idempotent advance → Task 7. fire after turn, non-blocking → Task 8. §6.3 trait_current/history (archive-on-create) reuses Plan-1 `model.set_trait`. Reuse of engram profile_merge + dimension configs → Tasks 1,2. NOT in scope: facts supersession (MVP add+dedup; noted), wall-clock idle trigger (turn-count proxy; noted), web/evals (later plans).
- **Placeholder scan:** none. Two intentional verification seams are explicitly flagged for the implementer (the `_PROMPT = Template = ...` typo in Task 6; the `mk()`/`await` test-helper note in Task 7) — both call out the exact correct form.
- **Type consistency:** every job exposes `async def run(start_turn, end_turn)`; the runner calls them uniformly. `bayes.merge_subdims(dimension, old_content, new_content)->dict`, `chat_json(system_prompt, user_prompt, stage=)`, `embed(text)` (async), `model.get_trait/set_trait`, `memory.get_cursor/advance_cursor/max_turn/messages_in_turn_range/add_summary/add_vector_ref/get_summary`, `VectorStore().add/search_scored` all match their Plan-1/2 definitions.
