# Vellum Eval Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An evaluation framework that measures whether Vellum actually works: **recall** quality (golden set → recall@k), **trait** modeling fidelity **per dimension, in isolation** (does a focused signal move the target sub-dimension the right way without spurious crosstalk), **facts** capture (fact-recall), **dossier** fidelity (holistic persona → LLM judge), and the **altitude** guard (impersonal questions must not drag in the personal model). Harness logic is keyless + unit-tested (mocked); real eval runs go through a CLI and need keys.

**Architecture:** A new `evals/` package under `api/` (importable as `evals.*`, alongside `app.*`). Each eval = (a) pure scoring/matching logic, unit-tested with mocks in the pytest suite; (b) a real-run entrypoint invoked via `python -m evals.run <name>` that exercises the real system + real models. The **external evaluator model** (generation + judging) is configured separately as `EVAL_GEN_*` and the framework **refuses to run if it equals the system model `LLM_*`** (kills the self-answering circularity — user requirement). Trait eval is **dimension-agnostic**: it iterates `DIMENSION_MAP`, so adding a pluggable dimension + its case file is automatically covered. Datasets are human-readable JSON the user curates.

**Tech Stack:** Same. Eval gen/judge are thin OpenAI-compatible httpx callers using `EVAL_GEN_*`. Evals are NOT in the default pytest run (slow/key-dependent); only their mocked harness tests are.

**Depends on (all merged to `main`):** `app.chat.{ingest,retrieval,assemble,respond}`, `app.model_loop.{traits,facts,dossier,runner}`, `app.store.{memory,model,vectors}`, `app.config.dimensions_loader.DIMENSION_MAP`, `app.llm.{client,embed}`.

**Spec:** `docs/specs/2026-06-06-vellum-design.md` §11 (评测), §3 (altitude).

Commands from `/Users/wangyuhao/Develop/personal/vellum/api`, python = `.venv/bin/python`.

---

## DESIGN DECISIONS BAKED IN (review these)

1. **External evaluator model `EVAL_GEN_*`, distinct from `LLM_*`, enforced.** Generation AND judging use `EVAL_GEN_*`; the system-under-test uses `LLM_*`. `evals.config.enforce_distinct_model()` raises if the two model ids match.
2. **Trait eval is per-dimension + isolated + dimension-agnostic.** One focused conversation per (dimension, sub-dimension, direction); run the real trait job over it; assert the target moved the right way AND non-targets didn't swing past a crosstalk tolerance. Iterates `DIMENSION_MAP`; new dimensions just add a case file.
3. **dossier eval keeps a holistic persona** (it's inherently holistic) → judge score 0–10 against the spec.
4. **fact-recall matching = normalized containment** in the harness (keyless, deterministic). Real runs may additionally use a judge; Plan 4 ships the containment matcher.
5. **Evals run via CLI, not pytest.** `python -m evals.run <recall|traits|facts|dossier|altitude|all>`. Generated conversation fixtures are committed (generate-once, reproducible, reviewable).
6. **Starter datasets are small** (1–3 cases each) and committed for the user to review/expand. Trait cases ship a committed generated conversation so they run without re-generating.

---

## File Structure

```
api/evals/
  __init__.py
  config.py          # EVAL_GEN_* resolution + enforce_distinct_model()
  gen.py             # generate user-message conversations via EVAL_GEN_* (key)
  judge.py           # llm_judge(prompt)->{score,...} via EVAL_GEN_* (key)
  recall.py          # recall@k over golden cases
  traits.py          # per-dimension direction + crosstalk scoring
  facts.py           # fact-recall (normalized containment)
  dossier.py         # holistic persona -> judge
  altitude.py        # impersonal Qs -> judge "no psychoanalysis"
  run.py             # CLI dispatcher
  data/
    recall_cases.json
    facts_cases.json
    altitude_questions.json
    personas/maya_founder.json
    traits/ocean_O_high.json          # + generated conversation committed inside
tests/  (in api/tests/, mocked, keyless — part of pytest)
  test_eval_config.py · test_eval_recall.py · test_eval_traits.py
  test_eval_facts.py · test_eval_judge.py
```

---

## Task 1: Eval config + distinct-model enforcement

**Files:** Create `api/evals/__init__.py`, `api/evals/config.py`; Test `api/tests/test_eval_config.py`

- [ ] **Step 1: Create `api/evals/__init__.py`** (empty)

- [ ] **Step 2: Write the failing test `api/tests/test_eval_config.py`**

```python
import pytest

from evals import config as ec


def test_resolves_eval_gen(monkeypatch):
    monkeypatch.setenv("EVAL_GEN_BASE_URL", "https://eval.test/v1")
    monkeypatch.setenv("EVAL_GEN_API_KEY", "k")
    monkeypatch.setenv("EVAL_GEN_MODEL", "judge-model")
    cfg = ec.eval_gen_config()
    assert cfg["model"] == "judge-model" and cfg["base_url"] == "https://eval.test/v1"


def test_enforce_distinct_raises_when_same(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "same-model")
    monkeypatch.setenv("EVAL_GEN_MODEL", "same-model")
    monkeypatch.setenv("EVAL_GEN_API_KEY", "k")
    monkeypatch.setenv("EVAL_GEN_BASE_URL", "https://eval.test/v1")
    with pytest.raises(RuntimeError, match="must differ"):
        ec.enforce_distinct_model()


def test_enforce_distinct_ok_when_different(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "system-model")
    monkeypatch.setenv("EVAL_GEN_MODEL", "judge-model")
    monkeypatch.setenv("EVAL_GEN_API_KEY", "k")
    monkeypatch.setenv("EVAL_GEN_BASE_URL", "https://eval.test/v1")
    ec.enforce_distinct_model()   # must not raise
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eval_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evals.config'`

- [ ] **Step 4: Create `api/evals/config.py`**

```python
"""External-evaluator model config. Generation + judging use EVAL_GEN_*, which
MUST differ from the system-under-test model (LLM_*) — otherwise a model would
grade its own work. Mirrors the LLM_* preset fallback shape loosely; for evals we
require explicit EVAL_GEN_BASE_URL / EVAL_GEN_API_KEY / EVAL_GEN_MODEL."""
import os

from app.llm.client import resolve_structured_llm_config


def eval_gen_config() -> dict:
    return {
        "base_url": (os.getenv("EVAL_GEN_BASE_URL") or "").strip().rstrip("/"),
        "api_key": (os.getenv("EVAL_GEN_API_KEY") or "").strip(),
        "model": (os.getenv("EVAL_GEN_MODEL") or "").strip(),
    }


def is_configured() -> bool:
    c = eval_gen_config()
    return bool(c["base_url"] and c["api_key"] and c["model"])


def enforce_distinct_model() -> None:
    """Refuse to run if the evaluator model equals the system model."""
    if not is_configured():
        raise RuntimeError(
            "Eval generator not configured. Set EVAL_GEN_BASE_URL / EVAL_GEN_API_KEY "
            "/ EVAL_GEN_MODEL (a model DIFFERENT from LLM_MODEL)."
        )
    system_model = resolve_structured_llm_config().get("model", "")
    if eval_gen_config()["model"] == system_model:
        raise RuntimeError(
            f"EVAL_GEN_MODEL and the system LLM_MODEL must differ (both are "
            f"{system_model!r}) — using the same model to generate and grade defeats the eval."
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_eval_config.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(evals): config + distinct evaluator-model enforcement"
```

---

## Task 2: Recall eval (golden set → recall@k)

**Files:** Create `api/evals/recall.py`, `api/evals/data/recall_cases.json`; Test `api/tests/test_eval_recall.py`

- [ ] **Step 1: Create starter `api/evals/data/recall_cases.json`** (review/expand later)

```json
[
  {
    "name": "offer_decision",
    "corpus": [
      {"role": "user", "content": "I got a startup offer but I'm scared it's unstable"},
      {"role": "assistant", "content": "weigh autonomy against security; what does the floor look like"},
      {"role": "user", "content": "my cat threw up on the rug this morning"},
      {"role": "user", "content": "the weather has been grey all week"}
    ],
    "query": "what did we discuss about that job offer",
    "expect_turns": [0]
  }
]
```

- [ ] **Step 2: Write the failing test `api/tests/test_eval_recall.py`**

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eval_recall.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evals.recall'`

- [ ] **Step 4: Create `api/evals/recall.py`**

```python
"""Recall eval: seed a corpus into a fresh stream, run the real retrieval for a
query, and check the expected turn(s) fall within the recalled windows."""
import json
from pathlib import Path

from app.chat import ingest, retrieval

_DATA = Path(__file__).parent / "data" / "recall_cases.json"


async def _seed(corpus: list[dict]) -> None:
    for m in corpus:
        if m["role"] == "user":
            await ingest.persist_user(m["content"])
        else:
            ingest.persist_assistant(m["content"])


async def run_case(case: dict, k: int, min_sim: float) -> dict:
    await _seed(case["corpus"])
    snippets = await retrieval.retrieve(case["query"], k=k, min_sim=min_sim)
    covered = set()
    for s in snippets:
        covered.update(range(s["start"], s["end"] + 1))
    expected = set(case["expect_turns"])
    found = expected & covered
    return {
        "name": case.get("name", "?"),
        "hit": expected.issubset(covered),
        "recall": (len(found) / len(expected)) if expected else 1.0,
    }


def load_cases() -> list[dict]:
    return json.loads(_DATA.read_text())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_eval_recall.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(evals): recall@k golden-set eval + starter case"
```

---

## Task 3: Trait eval (per-dimension, direction + crosstalk)

**Files:** Create `api/evals/traits.py`, `api/evals/data/traits/ocean_O_high.json`; Test `api/tests/test_eval_traits.py`

- [ ] **Step 1: Create starter `api/evals/data/traits/ocean_O_high.json`** (the committed `conversation` is a placeholder you will later regenerate via the CLI with the external model; it must SHOW high openness, not state it)

```json
{
  "dimension": "ocean",
  "target": {"sub": "O", "direction": "high"},
  "crosstalk_tolerance": 25,
  "conversation": [
    "I rearranged my whole weekend to try that experimental fermentation workshop — totally unfamiliar, no idea if I'd be any good, but the not-knowing is the fun part",
    "lately I keep pulling threads from totally unrelated fields, music theory into my data work, just to see what cross-pollinates",
    "a friend offered the safe familiar plan and I felt my energy drain; I'd rather chase the strange option and figure it out as I go"
  ]
}
```

- [ ] **Step 2: Write the failing test `api/tests/test_eval_traits.py`**

```python
import pytest

from evals import traits as et
from app.store import model


@pytest.mark.asyncio
async def test_direction_scoring_high(migrated_db, monkeypatch):
    # mock extraction: strong O-high signal, others null
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        return {"O": {"score": 88, "confidence": 0.7, "evidence": "x"},
                "C": None, "E": None, "A": None, "N": None}
    monkeypatch.setattr(et.traits_job, "chat_json", fake_chat_json)
    monkeypatch.setattr(et.traits_job, "DIMENSION_MAP",
                        {"ocean": et.traits_job.DIMENSION_MAP["ocean"]})

    case = {"dimension": "ocean", "target": {"sub": "O", "direction": "high"},
            "crosstalk_tolerance": 25,
            "conversation": ["I love unfamiliar experiments", "I chase strange ideas"]}
    result = await et.run_case(case)
    assert result["direction_ok"] is True
    assert result["crosstalk_ok"] is True       # others stayed near prior (no signal)


def test_direction_check_pure():
    assert et.direction_ok("high", 65) is True
    assert et.direction_ok("high", 45) is False
    assert et.direction_ok("low", 30) is True
    assert et.direction_ok("mid", 50) is True
    assert et.direction_ok("mid", 80) is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eval_traits.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evals.traits'`

- [ ] **Step 4: Create `api/evals/traits.py`**

```python
"""Per-dimension trait eval: feed a conversation engineered to express ONE
target (dimension, sub-dimension, direction), run the REAL trait job, then check
the target moved the right way and non-target sub-dimensions did not swing past a
crosstalk tolerance. Dimension-agnostic — driven by the case's `dimension`."""
import json
from pathlib import Path

from app.config.dimensions_loader import DIMENSION_MAP
from app.model_loop import traits as traits_job
from app.store import memory, model

_DATA = Path(__file__).parent / "data" / "traits"


def direction_ok(direction: str, score: float) -> bool:
    if direction == "high":
        return score >= 60
    if direction == "low":
        return score <= 40
    return 40 <= score <= 60            # mid


async def run_case(case: dict) -> dict:
    dim = case["dimension"]
    target_sub = case["target"]["sub"]
    direction = case["target"]["direction"]
    tol = case.get("crosstalk_tolerance", 25)

    prior = DIMENSION_MAP[dim].get("score_range", [0, 100])
    prior_mid = (prior[0] + prior[1]) / 2

    end = -1
    for line in case["conversation"]:
        end = memory.append_message("user", line)["turn"]
    await traits_job.run(0, end)

    cur = model.get_trait(dim)
    content = cur["content_json"] if cur else {}
    target_score = content.get(target_sub, {}).get("score")

    crosstalk_ok = True
    for sub, val in content.items():
        if sub == target_sub or not isinstance(val, dict) or "score" not in val:
            continue
        if abs(val["score"] - prior_mid) > tol:
            crosstalk_ok = False

    return {
        "dimension": dim, "target_sub": target_sub, "direction": direction,
        "target_score": target_score,
        "direction_ok": target_score is not None and direction_ok(direction, target_score),
        "crosstalk_ok": crosstalk_ok,
    }


def load_cases() -> list[dict]:
    if not _DATA.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(_DATA.glob("*.json"))]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_eval_traits.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(evals): per-dimension trait eval (direction + crosstalk) + starter case"
```

---

## Task 4: Facts eval (fact-recall)

**Files:** Create `api/evals/facts.py`, `api/evals/data/facts_cases.json`; Test `api/tests/test_eval_facts.py`

- [ ] **Step 1: Create starter `api/evals/data/facts_cases.json`**

```json
[
  {
    "name": "basics",
    "conversation": [
      "just so you know I'm allergic to penicillin",
      "my younger sister Lin is visiting from Shanghai next week",
      "anyway the weather's been grey"
    ],
    "expect_facts": ["allergic to penicillin", "sister", "Shanghai"]
  }
]
```

- [ ] **Step 2: Write the failing test `api/tests/test_eval_facts.py`**

```python
import pytest

from evals import facts as ef
from app.store import memory


def test_fact_recall_matcher():
    actual = ["allergic to penicillin", "has a sister named Lin in Shanghai"]
    expect = ["allergic to penicillin", "sister", "Shanghai", "vegetarian"]
    score = ef.fact_recall(expect, actual)
    assert score["recall"] == 0.75            # 3 of 4 matched by containment


@pytest.mark.asyncio
async def test_run_case_uses_real_facts_job(migrated_db, monkeypatch):
    async def fake_chat_json(system_prompt, user_prompt="", **kw):
        return {"facts": ["allergic to penicillin", "has a sister Lin in Shanghai"]}
    monkeypatch.setattr(ef.facts_job, "chat_json", fake_chat_json)
    case = {"conversation": ["I'm allergic to penicillin; sister Lin in Shanghai"],
            "expect_facts": ["penicillin", "Shanghai"]}
    result = await ef.run_case(case)
    assert result["recall"] == 1.0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eval_facts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evals.facts'`

- [ ] **Step 4: Create `api/evals/facts.py`**

```python
"""Facts eval: run the real facts job over a conversation with planted facts,
then measure fact-recall by normalized containment (an expected fact counts as
recalled if its lowercased text appears within any captured fact, or vice-versa)."""
import json
from pathlib import Path

from app.model_loop import facts as facts_job
from app.store import memory, model

_DATA = Path(__file__).parent / "data" / "facts_cases.json"


def fact_recall(expected: list[str], actual: list[str]) -> dict:
    al = [a.lower() for a in actual]
    matched = [e for e in expected
               if any(e.lower() in a or a in e.lower() for a in al)]
    return {"recall": (len(matched) / len(expected)) if expected else 1.0,
            "matched": matched, "missed": [e for e in expected if e not in matched]}


async def run_case(case: dict) -> dict:
    end = -1
    for line in case["conversation"]:
        end = memory.append_message("user", line)["turn"]
    await facts_job.run(0, end)
    actual = [f["text"] for f in model.active_facts()]
    return {"name": case.get("name", "?"), **fact_recall(case["expect_facts"], actual),
            "actual": actual}


def load_cases() -> list[dict]:
    return json.loads(_DATA.read_text())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_eval_facts.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(evals): facts eval (fact-recall by containment) + starter case"
```

---

## Task 5: Judge + dossier eval + altitude eval

**Files:** Create `api/evals/judge.py`, `api/evals/dossier.py`, `api/evals/altitude.py`, `api/evals/data/personas/maya_founder.json`, `api/evals/data/altitude_questions.json`; Test `api/tests/test_eval_judge.py`

- [ ] **Step 1: Create `api/evals/data/personas/maya_founder.json`**

```json
{
  "name": "maya_founder",
  "summary": "Seed-stage founder; values autonomy over security but is dogged by fear of failure; high openness, high conscientiousness, introverted, emotionally intense.",
  "facts": ["seed-stage startup founder", "younger sister named Lin", "based in Shanghai"]
}
```

- [ ] **Step 2: Create `api/evals/data/altitude_questions.json`**

```json
[
  "how do I vertically center a div in CSS",
  "what's the difference between TCP and UDP",
  "convert 30 celsius to fahrenheit"
]
```

- [ ] **Step 3: Write the failing test `api/tests/test_eval_judge.py`** (judge parsing is the keyless-testable part)

```python
import pytest

from evals import judge


@pytest.mark.asyncio
async def test_judge_parses_score(monkeypatch):
    async def fake_eval_chat(prompt):
        return '{"score": 8, "reason": "captures autonomy + fear of failure"}'
    monkeypatch.setattr(judge, "_eval_chat", fake_eval_chat)
    out = await judge.score("rubric...", "subject...")
    assert out["score"] == 8


@pytest.mark.asyncio
async def test_judge_handles_fenced_json(monkeypatch):
    async def fake_eval_chat(prompt):
        return "```json\n{\"score\": 3}\n```"
    monkeypatch.setattr(judge, "_eval_chat", fake_eval_chat)
    out = await judge.score("r", "s")
    assert out["score"] == 3
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_eval_judge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'evals.judge'`

- [ ] **Step 5: Create `api/evals/judge.py`**

```python
"""LLM-as-judge using the external evaluator model (EVAL_GEN_*). Returns a parsed
verdict dict (expects a JSON object with at least a numeric `score`)."""
import json

import httpx

from evals.config import eval_gen_config


async def _eval_chat(prompt: str) -> str:
    cfg = eval_gen_config()
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "stream": False,
                  "messages": [{"role": "user", "content": prompt}]},
        )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1 and e > s:
            return json.loads(text[s:e + 1])
        raise


async def score(rubric: str, subject: str) -> dict:
    prompt = f"{rubric}\n\n## Subject to evaluate\n{subject}\n\nRespond with a single JSON object."
    return _extract_json(await _eval_chat(prompt))
```

- [ ] **Step 6: Create `api/evals/dossier.py`**

```python
"""Dossier eval (holistic): the system builds a dossier from a persona's
conversation; an external judge scores 0-10 how well it captures the persona."""
import json
from pathlib import Path

from app.store import model
from evals import judge

_DATA = Path(__file__).parent / "data" / "personas"

_RUBRIC = (
    "You are grading how well an AI's portrait of a user matches the TRUE persona. "
    "Score 0-10 (10 = captures the persona's values/patterns with no contradictions). "
    "Penalize contradictions and generic filler. Respond JSON: {\"score\": <0-10>, \"reason\": \"...\"}.\n\n"
    "## True persona\n{persona}"
)


async def run_persona(name: str) -> dict:
    spec = json.loads((_DATA / f"{name}.json").read_text())
    dossier_text = model.get_dossier()
    rubric = _RUBRIC.replace("{persona}", json.dumps(spec, ensure_ascii=False))
    verdict = await judge.score(rubric, dossier_text or "(empty dossier)")
    return {"persona": name, "score": verdict.get("score"), "reason": verdict.get("reason")}
```

- [ ] **Step 7: Create `api/evals/altitude.py`**

```python
"""Altitude guard: with a RICH personal model loaded, ask impersonal questions
and have an external judge confirm the answer did NOT drag in the user's
personality/history (spec §3 — the current question is the figure)."""
import json
from pathlib import Path

from app.chat import assemble, respond
from app.store import memory
from evals import judge

_Q = Path(__file__).parent / "data" / "altitude_questions.json"

_RUBRIC = (
    "An assistant that secretly knows the user was asked a PURELY TECHNICAL/FACTUAL "
    "question. Did it inappropriately bring up the user's personality, traits, "
    "feelings, or personal history? Respond JSON: {\"psychoanalyzed\": true|false, "
    "\"reason\": \"...\"}."
)


async def run_question(q: str) -> dict:
    memory.append_message("user", q)
    messages = await assemble.build_messages(query=q)
    answer = ""
    async for ev in respond.stream(messages):
        if ev["type"] == "final":
            answer = ev["content"]
    verdict = await judge.score(_RUBRIC, f"Question: {q}\nAnswer: {answer}")
    return {"q": q, "passed": verdict.get("psychoanalyzed") is False, "answer": answer}


def load_questions() -> list[str]:
    return json.loads(_Q.read_text())
```

- [ ] **Step 8: Run the judge tests, verify pass**

Run: `.venv/bin/python -m pytest tests/test_eval_judge.py -v`
Expected: 2 passed

- [ ] **Step 9: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(evals): judge + dossier (holistic) + altitude guard"
```

---

## Task 6: Generation helper + CLI runner

**Files:** Create `api/evals/gen.py`, `api/evals/run.py`; (no new pytest — these are key-dependent real-run entrypoints, smoke-verified by import)

- [ ] **Step 1: Create `api/evals/gen.py`**

```python
"""Generate a synthetic conversation that ENACTS a target (show, don't tell),
using the external evaluator model EVAL_GEN_*. Used to (re)author committed trait
conversation fixtures and persona conversations."""
import httpx

from evals.config import eval_gen_config, enforce_distinct_model


async def generate_conversation(instruction: str, n: int = 6) -> list[str]:
    enforce_distinct_model()
    cfg = eval_gen_config()
    prompt = (
        f"Produce exactly {n} first-person user messages (a person talking to an AI) "
        f"that AUTHENTICALLY ENACT the following, WITHOUT ever naming the trait or "
        f"stating it directly — show it through concrete situations, choices, and tone:\n\n"
        f"{instruction}\n\nRespond as strict JSON: {{\"messages\": [\"...\", ...]}}."
    )
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json={"model": cfg["model"], "stream": False,
                  "messages": [{"role": "user", "content": prompt}]},
        )
    resp.raise_for_status()
    import json
    content = resp.json()["choices"][0]["message"]["content"]
    s, e = content.find("{"), content.rfind("}")
    return json.loads(content[s:e + 1])["messages"]
```

- [ ] **Step 2: Create `api/evals/run.py`** (CLI; each eval uses a fresh in-memory-ish DB via a temp data dir)

```python
"""CLI: python -m evals.run <recall|traits|facts|dossier|altitude|all>

Real eval runner. Requires LLM_* (system under test) and EVAL_GEN_* (external
evaluator, distinct model). Each case runs against a fresh temp data dir so cases
don't contaminate each other or your real data."""
import asyncio
import os
import sys
import tempfile

from evals import config as ec


def _fresh_data_dir():
    d = tempfile.mkdtemp(prefix="vellum-eval-")
    os.environ["VELLUM_DATA_DIR"] = d
    from app.store import db
    db.run_migrations()


async def _recall():
    from evals import recall
    out = []
    for case in recall.load_cases():
        _fresh_data_dir()
        out.append(await recall.run_case(case, k=6, min_sim=0.35))
    return out


async def _traits():
    from evals import traits
    out = []
    for case in traits.load_cases():
        _fresh_data_dir()
        out.append(await traits.run_case(case))
    return out


async def _facts():
    from evals import facts
    out = []
    for case in facts.load_cases():
        _fresh_data_dir()
        out.append(await facts.run_case(case))
    return out


async def _altitude():
    from evals import altitude
    ec.enforce_distinct_model()
    out = []
    for q in altitude.load_questions():
        _fresh_data_dir()
        out.append(await altitude.run_question(q))
    return out


_EVALS = {"recall": _recall, "traits": _traits, "facts": _facts, "altitude": _altitude}


async def _main(which: str):
    names = list(_EVALS) if which == "all" else [which]
    for name in names:
        results = await _EVALS[name]()
        print(f"\n=== {name} ===")
        for r in results:
            print(r)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    asyncio.run(_main(which))
```

> NOTE: `dossier` is intentionally not in the CLI map yet — it requires first running a persona's conversation through modeling to populate the dossier. Wire a `_dossier()` that (1) generates/loads the persona conversation, (2) runs `model_loop.runner` over it, (3) calls `evals.dossier.run_persona`, once you've authored a persona conversation fixture with `gen.generate_conversation`. Left as the first follow-up so this plan stays bounded.

- [ ] **Step 3: Smoke-verify imports**

Run: `.venv/bin/python -c "import evals.run, evals.gen, evals.dossier, evals.altitude, evals.traits, evals.recall, evals.facts, evals.judge, evals.config; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Run the FULL pytest suite (evals' mocked harness tests included; real evals NOT run)**

Run: `.venv/bin/python -m pytest -q`
Expected: all prior (61) + new eval harness tests pass.

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(evals): generation helper + CLI runner"
```

- [ ] **Step 6: Document running evals** — append to `api/.env.example`:

```bash
# Eval framework (only needed to RUN evals; harness tests are keyless):
# external evaluator model — MUST differ from LLM_MODEL
EVAL_GEN_BASE_URL=https://api.openai.com/v1
EVAL_GEN_API_KEY=
EVAL_GEN_MODEL=gpt-4.1
```

and commit:
```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "docs(evals): document EVAL_GEN_* in .env.example"
```

---

## Done criteria

- `python -m pytest -q` green (eval harness logic tested, mocked, keyless).
- `python -m evals.run recall|traits|facts|altitude` runs against real models when `LLM_*` + `EVAL_GEN_*` are set; refuses if the two models are equal.
- Datasets are small committed JSON the user can review/expand; trait eval is dimension-agnostic (add a `data/traits/<dim>_<sub>_<dir>.json` and it's covered).
- Follow-ups (noted, out of scope): `_dossier()` CLI wiring after authoring a persona conversation; judge-based fact matching; tool-call eval.

---

## Self-Review

- **Spec coverage:** §11 recall (golden, recall@k) → Task 2. trait fidelity, **per-dimension isolated + crosstalk + dimension-agnostic** → Task 3. facts → Task 4. dossier holistic + judge → Task 5. altitude guard → Task 5/6. external evaluator distinct-model enforcement → Task 1 (+ used in gen/altitude). keyless harness in pytest vs key-gated CLI runs → all tasks (mocked tests) + Task 6 (CLI). §3 altitude → Task 5 altitude rubric.
- **Placeholder scan:** none in code. One scoped follow-up is explicitly flagged (`_dossier()` CLI wiring) with the exact steps to complete it — not a hidden gap. Trait `conversation` fixtures are real starter data the user will refine (and can regenerate via `gen.py`).
- **Type consistency:** `run_case(case)->dict` shape consistent across recall/traits/facts; `judge.score(rubric, subject)->dict`; `eval_gen_config()->{base_url,api_key,model}`; `enforce_distinct_model()` used by gen + altitude + (recommended) every real run. `evals.traits` imports the modeling job as `traits_job` to avoid name collision with the eval module — referenced consistently in the test monkeypatch (`et.traits_job.chat_json`, `et.traits_job.DIMENSION_MAP`).
