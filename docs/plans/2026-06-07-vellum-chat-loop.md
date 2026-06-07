# Vellum Chat Consume Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A working `POST /chat` that streams a reply (SSE) grounded in the personal model + long-term memory, with hybrid recall — A (framework, always-on, threshold-gated) + B (a model-driven `recall_memory` tool via a generic tool registry) — and graceful A-only degradation for models weak at tool calling. Altitude: the current question is the figure; personal model/memory are background reference.

**Architecture:** Built on the merged foundation (Plan 1). The chat route persists the user turn (+embeds it), `assemble.py` builds the context (persona + altitude instruction + background reference: dossier / active facts / trait summary / A-retrieved snippets + recent tail), `respond.py` streams via the ported `chat_with_tools_stream`, dispatching any `tool_call` through a generic `tools/registry` (the only registered tool this plan adds is `recall_memory`). Both A and B reuse one `retrieval.py`. Reads the personal model but does NOT update it (that's Plan 3).

**Tech Stack:** Same as foundation. FastAPI `StreamingResponse` for SSE.

**Depends on (foundation API, already on `main`):**
- `app.store.memory`: `append_message(role,content)->{id,turn}`, `recent_tail(limit)`, `messages_in_turn_range(a,b)`, `add_vector_ref(ref_type,ref_id)->label`, `resolve_vector_ref(label)`, `get_summary(id)`
- `app.store.model`: `get_dossier()`, `active_facts()`, `get_trait(dim)`, (trait_current rows enumerable)
- `app.store.vectors`: `VectorStore().add(label,emb,save=)`, `.search(emb,k)` (extended here to also score)
- `app.store.traces`: `record(...)`
- `app.llm.client`: `chat_with_tools_stream(messages,tools,...)`, `resolve_structured_llm_config()`, `_PROVIDER_CAPS`
- `app.llm.embed`: `embed(text)->list[float]`

**Spec:** `docs/specs/2026-06-06-vellum-design.md` §3 (高度), §5 (接入层), §7 (消费回路).

All commands run from `/Users/wangyuhao/Develop/personal/vellum/api` with the venv: prefix python as `.venv/bin/python`.

---

## File Structure

```
api/app/
  config.py                 # + chat tunables (tail/k/threshold/W/recall hops/persona)
  chat/
    __init__.py
    retrieval.py            # A/B shared: embed->search->resolve->hydrate->dedup->threshold
    persona.py              # load persona text (default neutral, env-switchable)
    assemble.py             # build LLM messages (persona+altitude+references+tail)
    respond.py              # stream + tool loop + A-only degradation; persist assistant; trace
    ingest.py               # persist user (+embed+vector) / persist assistant
    tools/
      __init__.py
      registry.py           # generic tool registry + dispatch
      recall.py             # recall_memory tool (schema + handler)
  config/persona/neutral.txt
  llm/client.py             # + tool-calling capability flag + empty-tools guard
  store/vectors.py          # + search_scored()
  routes/__init__.py
  routes/chat.py            # POST /chat (SSE)
  main.py                   # include chat router
tests/
  test_vectors_scored.py · test_retrieval.py · test_persona.py · test_assemble.py
  test_tools.py · test_respond.py · test_ingest.py · test_chat_route.py
```

---

## Task 1: Scored vector search

The foundation's `VectorStore.search` returns labels only; A's threshold gate needs similarity. Add a scored variant (cosine: similarity = 1 − distance).

**Files:** Modify `api/app/store/vectors.py`; Test `api/tests/test_vectors_scored.py`

- [ ] **Step 1: Write the failing test `api/tests/test_vectors_scored.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vectors_scored.py -v`
Expected: FAIL — `AttributeError: 'VectorStore' object has no attribute 'search_scored'`

- [ ] **Step 3: Add `search_scored` to `api/app/store/vectors.py`** (insert after `search`)

```python
    def search_scored(self, embedding: list[float], k: int = 5) -> list[tuple[int, float]]:
        """Like search() but returns (label, cosine_similarity) pairs, highest first.
        hnswlib cosine 'distance' = 1 - similarity, so similarity = 1 - distance."""
        if self.index is None or self.index.get_current_count() == 0:
            return []
        if self.dim is not None and len(embedding) != self.dim:
            raise ValueError(f"Query dim {len(embedding)} != index dim {self.dim}")
        labels, distances = self.index.knn_query(
            np.array([embedding], dtype=np.float32),
            k=min(k, self.index.get_current_count()),
        )
        return [(int(l), 1.0 - float(d)) for l, d in zip(labels[0], distances[0])]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_vectors_scored.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: scored vector search (label + cosine similarity)"
```

---

## Task 2: Tool-calling capability flag + empty-tools guard

**Files:** Modify `api/app/llm/client.py`; Test `api/tests/test_tool_capability.py`

- [ ] **Step 1: Write the failing test `api/tests/test_tool_capability.py`**

```python
from app.llm import client as llm


def test_known_provider_tool_capability(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert llm.provider_supports_tools() is True


def test_unknown_provider_defaults_true(monkeypatch):
    # Custom base_url, no preset → optimistic default (we degrade at runtime if it 400s)
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    assert llm.provider_supports_tools() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tool_capability.py -v`
Expected: FAIL — `AttributeError: module 'app.llm.client' has no attribute 'provider_supports_tools'`

- [ ] **Step 3: Edit `api/app/llm/client.py`**

3a. Add a `tool_calling` key to each entry of the existing `_PROVIDER_CAPS` dict. Use `True` for providers the engram matrix lists as supporting tools (openai, anthropic, gemini, grok, deepseek, moonshot, qwen, glm, minimax, ark, ollama) and `True` for openrouter as well (it's model-dependent; we degrade at runtime). Example for one entry:

```python
    "openai":     {"json_object": True,  "tested": False, "tool_calling": True},
```

Apply the same `"tool_calling": True` addition to every entry (single-user local; treat all presets as tool-capable, degrade at runtime on error).

3b. Add the helper near `_provider_supports_json_object`:

```python
def provider_supports_tools() -> bool:
    """Whether the configured provider is expected to support OpenAI-style tool
    calling. Unknown providers default True; respond.py degrades to A-only if a
    tool round actually errors at runtime."""
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower()
    return _PROVIDER_CAPS.get(provider, {}).get("tool_calling", True)
```

3c. In `chat_with_tools_stream`, make tools/tool_choice conditional so an empty tools list streams plain text (A-only). Change the payload construction from always including tools to:

```python
    payload = {
        "model": config["model"],
        "stream": True,
        "stream_options": {"include_usage": True},
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
```

(Leave the rest of the function unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tool_capability.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: tool-calling capability flag + empty-tools text-stream guard"
```

---

## Task 3: Chat config tunables

**Files:** Modify `api/app/config.py`; Test `api/tests/test_chat_config.py`

- [ ] **Step 1: Write the failing test `api/tests/test_chat_config.py`**

```python
from app import config


def test_defaults(monkeypatch):
    for k in ("VELLUM_TAIL_SIZE", "VELLUM_RECALL_K", "VELLUM_RECALL_MIN_SIM",
              "VELLUM_NEIGHBORHOOD_W", "VELLUM_RECALL_MAX_HOPS", "VELLUM_PERSONA"):
        monkeypatch.delenv(k, raising=False)
    assert config.tail_size() == 20
    assert config.recall_k() == 6
    assert 0.0 < config.recall_min_sim() < 1.0
    assert config.neighborhood_w() == 3
    assert config.recall_max_hops() == 3
    assert config.persona_name() == "neutral"


def test_env_override(monkeypatch):
    monkeypatch.setenv("VELLUM_TAIL_SIZE", "8")
    assert config.tail_size() == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chat_config.py -v`
Expected: FAIL — `AttributeError: module 'app.config' has no attribute 'tail_size'`

- [ ] **Step 3: Append to `api/app/config.py`**

```python
def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def tail_size() -> int:        return _int("VELLUM_TAIL_SIZE", 20)
def recall_k() -> int:         return _int("VELLUM_RECALL_K", 6)
def recall_min_sim() -> float: return _float("VELLUM_RECALL_MIN_SIM", 0.35)
def neighborhood_w() -> int:   return _int("VELLUM_NEIGHBORHOOD_W", 3)
def recall_max_hops() -> int:  return _int("VELLUM_RECALL_MAX_HOPS", 3)
def persona_name() -> str:     return os.getenv("VELLUM_PERSONA", "neutral")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_chat_config.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: chat config tunables"
```

---

## Task 4: Retrieval module (A/B shared)

**Files:** Create `api/app/chat/__init__.py`, `api/app/chat/retrieval.py`; Test `api/tests/test_retrieval.py`

- [ ] **Step 1: Create `api/app/chat/__init__.py`** (empty)

- [ ] **Step 2: Write the failing test `api/tests/test_retrieval.py`**

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_retrieval.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.chat.retrieval'`

- [ ] **Step 4: Create `api/app/chat/retrieval.py`**

```python
"""Hybrid-recall core (shared by A framework-retrieval and B recall tool).

Pipeline: embed(query) -> vector search (scored) -> threshold gate ->
resolve labels to sources -> hydrate turn-neighbourhoods (message hits pull the
surrounding window INCLUDING assistant turns; summary hits use the digest +
optionally its range) -> dedup overlapping windows."""
import asyncio

from app import config
from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore


def _embed_sync(text: str) -> list[float]:
    """Sync wrapper around the async embed() so retrieval is callable from sync
    assembly code. (Tests monkeypatch this.)"""
    return asyncio.run(embed(text))


def _format_window(rows: list[dict]) -> str:
    return "\n".join(f"{r['role']}: {r['content']}" for r in rows)


def retrieve(query: str, k: int | None = None, min_sim: float | None = None,
             w: int | None = None) -> list[dict]:
    """Return reference snippets for `query`. Each snippet: {start, end, text}."""
    k = k if k is not None else config.recall_k()
    min_sim = min_sim if min_sim is not None else config.recall_min_sim()
    w = w if w is not None else config.neighborhood_w()

    hits = VectorStore().search_scored(_embed_sync(query), k=k)
    windows: list[tuple[int, int]] = []
    for label, sim in hits:
        if sim < min_sim:
            continue
        ref = memory.resolve_vector_ref(label)
        if not ref:
            continue
        if ref["ref_type"] == "message":
            rows = memory.messages_in_turn_range(0, 10**9)  # bounded below by anchor
            anchor = next((m for m in rows if m["id"] == ref["ref_id"]), None)
            if anchor is None:
                continue
            t = anchor["turn"]
            windows.append((max(0, t - w), t + w))
        elif ref["ref_type"] == "summary":
            s = memory.get_summary(ref["ref_id"])
            if s:
                windows.append((s["start_turn"], s["end_turn"]))

    # dedup / merge overlapping windows
    windows.sort()
    merged: list[list[int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    snippets = []
    for start, end in merged:
        rows = memory.messages_in_turn_range(start, end)
        if rows:
            snippets.append({"start": start, "end": end, "text": _format_window(rows)})
    return snippets
```

> NOTE for implementer: the `messages_in_turn_range(0, 10**9)` scan to find the anchor by id is O(stream). If that reads poorly to you, add a `memory.get_message(id)` helper in `store/memory.py` (one-line SELECT by id) and use it instead — report it as a small deviation. Either is acceptable; prefer the helper if you add it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_retrieval.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: hybrid-recall retrieval core (search + threshold + hydrate + dedup)"
```

---

## Task 5: Persona loader

**Files:** Create `api/app/config/persona/neutral.txt`, `api/app/chat/persona.py`; Test `api/tests/test_persona.py`

- [ ] **Step 1: Create `api/app/config/persona/neutral.txt`**

```
You are a clear-thinking, genuinely helpful assistant. You know this user well from a long shared history, but you are a capable general assistant first — not a therapist or a life coach. Be direct and useful.
```

- [ ] **Step 2: Write the failing test `api/tests/test_persona.py`**

```python
from app.chat import persona


def test_loads_neutral_by_default(monkeypatch):
    monkeypatch.delenv("VELLUM_PERSONA", raising=False)
    text = persona.load()
    assert "general assistant" in text


def test_unknown_persona_falls_back_to_neutral(monkeypatch):
    monkeypatch.setenv("VELLUM_PERSONA", "does-not-exist")
    assert "general assistant" in persona.load()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_persona.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.chat.persona'`

- [ ] **Step 4: Create `api/app/chat/persona.py`**

```python
from pathlib import Path

from app import config

_DIR = Path(__file__).resolve().parent.parent / "config" / "persona"


def load() -> str:
    name = config.persona_name()
    path = _DIR / f"{name}.txt"
    if not path.exists():
        path = _DIR / "neutral.txt"
    return path.read_text().strip()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_persona.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: persona loader (neutral default, env-switchable)"
```

---

## Task 6: Context assembly

**Files:** Create `api/app/chat/assemble.py`; Test `api/tests/test_assemble.py`

- [ ] **Step 1: Write the failing test `api/tests/test_assemble.py`**

```python
from app.chat import assemble
from app.store import memory, model


def test_build_messages_has_altitude_persona_and_tail(migrated_db, monkeypatch):
    monkeypatch.setattr(assemble.retrieval, "retrieve", lambda q, **kw: [])
    model.set_dossier("values autonomy")
    model.add_fact("allergic to penicillin")
    memory.append_message("user", "hello there")
    msgs = assemble.build_messages()
    system = msgs[0]["content"]
    assert msgs[0]["role"] == "system"
    assert "general assistant" in system            # persona
    assert "background reference" in system.lower()  # altitude framing
    assert "values autonomy" in system               # dossier
    assert "allergic to penicillin" in system        # facts
    assert msgs[-1] == {"role": "user", "content": "hello there"}   # tail tail


def test_retrieved_snippets_included(migrated_db, monkeypatch):
    monkeypatch.setattr(
        assemble.retrieval, "retrieve",
        lambda q, **kw: [{"start": 0, "end": 1, "text": "user: x\nassistant: y"}],
    )
    memory.append_message("user", "q")
    system = assemble.build_messages()[0]["content"]
    assert "assistant: y" in system
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.chat.assemble'`

- [ ] **Step 3: Create `api/app/chat/assemble.py`**

```python
"""Build the LLM `messages` payload for one chat turn. The current question is
the figure; the personal model + retrieved memory are BACKGROUND REFERENCE,
framed so the model leads with the answer and only leans on them when relevant
(spec §3 altitude)."""
from app import config
from app.chat import persona, retrieval
from app.store import memory, model
from app.store.db import get_conn

_ALTITUDE = (
    "Answer the user's CURRENT question directly and well. Everything below is "
    "BACKGROUND REFERENCE about the user — draw on it only when it genuinely "
    "helps the current question. Do not force it in, do not psychoanalyze the "
    "user, and do not bring up their traits or history unless it is relevant."
)


def _trait_summary() -> str:
    with get_conn() as conn:
        rows = conn.execute("SELECT dimension FROM trait_current").fetchall()
    parts = []
    for r in rows:
        t = model.get_trait(r["dimension"])
        if not t:
            continue
        scores = {k: v.get("score") for k, v in t["content_json"].items()
                  if isinstance(v, dict) and "score" in v}
        if scores:
            parts.append(f"{r['dimension']}: " +
                         " ".join(f"{k}={round(v)}" for k, v in scores.items()))
    return "\n".join(parts)


def build_messages(query: str | None = None) -> list[dict]:
    """Assemble system + recent tail. `query` for retrieval defaults to the last
    user message in the tail."""
    tail = memory.recent_tail(config.tail_size())
    if query is None:
        last_user = next((m for m in reversed(tail) if m["role"] == "user"), None)
        query = last_user["content"] if last_user else ""

    sections = [persona.load(), _ALTITUDE]

    dossier = model.get_dossier().strip()
    if dossier:
        sections.append("## What you know about the user\n" + dossier)

    facts = model.active_facts()
    if facts:
        sections.append("## Durable facts\n" + "\n".join(f"- {f['text']}" for f in facts))

    traits = _trait_summary()
    if traits:
        sections.append("## Personality signal (reference only)\n" + traits)

    if query:
        snips = retrieval.retrieve(query)
        if snips:
            sections.append("## Possibly relevant past\n" +
                            "\n---\n".join(s["text"] for s in snips))

    system = {"role": "system", "content": "\n\n".join(sections)}
    history = [{"role": m["role"], "content": m["content"]} for m in tail]
    return [system, *history]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_assemble.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: context assembly (persona + altitude + reference + tail)"
```

---

## Task 7: Generic tool registry + recall_memory tool

**Files:** Create `api/app/chat/tools/__init__.py`, `registry.py`, `recall.py`; Test `api/tests/test_tools.py`

- [ ] **Step 1: Create `api/app/chat/tools/__init__.py`** (empty)

- [ ] **Step 2: Write the failing test `api/tests/test_tools.py`**

```python
from app.chat.tools import registry, recall


def test_registry_dispatch():
    reg = registry.ToolRegistry()
    reg.register(
        schema={"type": "function",
                "function": {"name": "echo", "description": "echo",
                             "parameters": {"type": "object",
                                            "properties": {"x": {"type": "string"}}}}},
        handler=lambda args: f"got {args['x']}",
    )
    assert [t["function"]["name"] for t in reg.schemas()] == ["echo"]
    assert reg.dispatch("echo", {"x": "hi"}) == "got hi"


def test_recall_tool_registered_and_calls_retrieval(monkeypatch):
    monkeypatch.setattr(recall.retrieval, "retrieve",
                        lambda q, **kw: [{"start": 0, "end": 0, "text": "user: past thing"}])
    reg = registry.ToolRegistry()
    recall.register_into(reg)
    names = [t["function"]["name"] for t in reg.schemas()]
    assert "recall_memory" in names
    out = reg.dispatch("recall_memory", {"query": "past"})
    assert "past thing" in out
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.chat.tools.registry'`

- [ ] **Step 4: Create `api/app/chat/tools/registry.py`**

```python
"""Generic tool registry. A tool = (OpenAI-style schema, handler(args)->str).
The chat loop calls schemas() to advertise tools and dispatch() to run a call.
Adding a new tool later = register one entry; the loop never changes."""
from typing import Callable


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, schema: dict, handler: Callable[[dict], str]) -> None:
        name = schema["function"]["name"]
        self._tools[name] = {"schema": schema, "handler": handler}

    def schemas(self) -> list[dict]:
        return [t["schema"] for t in self._tools.values()]

    def dispatch(self, name: str, args: dict) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"ERROR: unknown tool {name!r}"
        try:
            return tool["handler"](args)
        except Exception as exc:  # tool failures must not crash the chat turn
            return f"ERROR running {name}: {exc}"
```

- [ ] **Step 5: Create `api/app/chat/tools/recall.py`**

```python
"""The recall_memory tool (B): lets the model issue a targeted/iterative memory
query with a well-formed search string."""
from app.chat import retrieval

_SCHEMA = {
    "type": "function",
    "function": {
        "name": "recall_memory",
        "description": (
            "Search the user's long-term memory for past conversations relevant "
            "to a query. Use when the user references something from the past, or "
            "when prior context would materially help — with a focused query "
            "(not the raw user message)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for."}
            },
            "required": ["query"],
        },
    },
}


def _handler(args: dict) -> str:
    snips = retrieval.retrieve(args.get("query", ""))
    if not snips:
        return "No relevant past conversations found."
    return "\n---\n".join(s["text"] for s in snips)


def register_into(reg) -> None:
    reg.register(schema=_SCHEMA, handler=_handler)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_tools.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: generic tool registry + recall_memory tool"
```

---

## Task 8: Ingest (persist user/assistant)

**Files:** Create `api/app/chat/ingest.py`; Test `api/tests/test_ingest.py`

- [ ] **Step 1: Write the failing test `api/tests/test_ingest.py`**

```python
import app.chat.ingest as ingest
from app.store import memory
from app.store.vectors import VectorStore


def test_persist_user_stores_and_embeds(migrated_db, monkeypatch):
    monkeypatch.setattr(ingest, "_embed_sync", lambda t: [1.0, 0.0, 0.0])
    res = ingest.persist_user("hello")
    assert res["turn"] == 0
    # message stored
    assert memory.recent_tail(1)[0]["content"] == "hello"
    # vector indexed + resolvable back to the message
    hits = VectorStore().search_scored([1.0, 0.0, 0.0], k=1)
    ref = memory.resolve_vector_ref(hits[0][0])
    assert ref["ref_type"] == "message" and ref["ref_id"] == res["id"]


def test_persist_assistant_stores_no_vector(migrated_db, monkeypatch):
    monkeypatch.setattr(ingest, "_embed_sync", lambda t: [1.0, 0.0, 0.0])
    ingest.persist_user("hi")                 # creates the index (dim=3)
    ingest.persist_assistant("hello back")
    assert memory.recent_tail(1)[0]["role"] == "assistant"
    # only the user vector exists
    assert VectorStore().index.get_current_count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.chat.ingest'`

- [ ] **Step 3: Create `api/app/chat/ingest.py`**

```python
"""Persist turns into the eternal stream. User turns are embedded + indexed
(searchable key); assistant turns are stored verbatim only (recalled via turn
linkage, never embedded — spec §6/§7)."""
import asyncio

from app.llm.embed import embed
from app.store import memory
from app.store.vectors import VectorStore


def _embed_sync(text: str) -> list[float]:
    return asyncio.run(embed(text))


def persist_user(content: str) -> dict:
    msg = memory.append_message("user", content)
    label = memory.add_vector_ref("message", msg["id"])
    VectorStore().add(label, _embed_sync(content))
    return msg


def persist_assistant(content: str) -> dict:
    return memory.append_message("assistant", content)  # no embed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ingest.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: ingest (persist user+embed / assistant no-embed)"
```

---

## Task 9: Respond orchestration (stream + tool loop + degradation)

**Files:** Create `api/app/chat/respond.py`; Test `api/tests/test_respond.py`

- [ ] **Step 1: Write the failing test `api/tests/test_respond.py`**

```python
import json
import pytest

import app.chat.respond as respond


async def _fake_stream_no_tool(messages, tools, **kw):
    yield {"type": "content_delta", "delta": "Hello "}
    yield {"type": "content_delta", "delta": "world"}
    yield {"type": "done", "finish_reason": "stop",
           "message": {"role": "assistant", "content": "Hello world"},
           "usage": {}, "duration_ms": 1}


async def _fake_stream_with_tool(messages, tools, **kw):
    # First round: call recall_memory; second round (after tool result): answer.
    if not any(m.get("role") == "tool" for m in messages):
        msg = {"role": "assistant", "content": None,
               "tool_calls": [{"id": "c1", "type": "function",
                               "function": {"name": "recall_memory",
                                            "arguments": json.dumps({"query": "offer"})}}]}
        yield {"type": "done", "finish_reason": "tool_calls", "message": msg,
               "usage": {}, "duration_ms": 1}
    else:
        yield {"type": "content_delta", "delta": "Per your past: "}
        yield {"type": "content_delta", "delta": "go for it"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "Per your past: go for it"},
               "usage": {}, "duration_ms": 1}


@pytest.mark.asyncio
async def test_stream_plain(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_stream_no_tool)
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: True)
    deltas, final = [], {}
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "delta":
            deltas.append(ev["text"])
        elif ev["type"] == "final":
            final = ev
    assert "".join(deltas) == "Hello world"
    assert final["content"] == "Hello world"


@pytest.mark.asyncio
async def test_tool_loop_runs_handler_and_continues(monkeypatch):
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", _fake_stream_with_tool)
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: True)
    monkeypatch.setattr(respond, "_build_registry",
                        lambda: _stub_registry(monkeypatch))
    out = []
    async for ev in respond.stream([{"role": "system", "content": "s"}]):
        if ev["type"] == "delta":
            out.append(ev["text"])
    assert "go for it" in "".join(out)


def _stub_registry(monkeypatch):
    from app.chat.tools import registry
    reg = registry.ToolRegistry()
    reg.register(
        schema={"type": "function", "function": {"name": "recall_memory",
                "description": "d", "parameters": {"type": "object", "properties": {}}}},
        handler=lambda args: "RECALLED CONTEXT",
    )
    return reg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_respond.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.chat.respond'`

- [ ] **Step 3: Create `api/app/chat/respond.py`**

```python
"""Stream one assistant reply. Hybrid recall: A retrieval is already baked into
the assembled `messages` (system reference). B = the recall_memory tool offered
here when the provider supports tools; if not, tools=[] and it streams plain
text (A-only degradation). Yields {"type":"delta","text":...} events during the
stream and one {"type":"final","content":...} at the end."""
import json

from app import config
from app.chat.tools import recall, registry
from app.llm import client as llm


def _build_registry() -> registry.ToolRegistry:
    reg = registry.ToolRegistry()
    recall.register_into(reg)
    return reg


async def stream(messages: list[dict]):
    reg = _build_registry() if llm.provider_supports_tools() else None
    tools = reg.schemas() if reg else []
    convo = list(messages)
    content_parts: list[str] = []

    for _hop in range(config.recall_max_hops() + 1):
        assistant_msg = None
        async for ev in llm.chat_with_tools_stream(messages=convo, tools=tools, stage="chat"):
            if ev["type"] == "content_delta":
                content_parts.append(ev["delta"])
                yield {"type": "delta", "text": ev["delta"]}
            elif ev["type"] == "done":
                assistant_msg = ev["message"]
                finish = ev["finish_reason"]

        convo.append(assistant_msg)
        if finish != "tool_calls" or not reg:
            break

        # run each requested tool, append results, loop for another model round
        for tc in assistant_msg.get("tool_calls") or []:
            fn = tc["function"]
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = reg.dispatch(fn["name"], args)
            convo.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

    yield {"type": "final", "content": "".join(content_parts)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_respond.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: respond orchestration (stream + tool loop + A-only degradation)"
```

---

## Task 10: Chat route (SSE) + wiring + integration

**Files:** Create `api/app/routes/__init__.py`, `api/app/routes/chat.py`; Modify `api/app/main.py`; Test `api/tests/test_chat_route.py`

- [ ] **Step 1: Create `api/app/routes/__init__.py`** (empty)

- [ ] **Step 2: Write the failing integration test `api/tests/test_chat_route.py`**

```python
import json

from fastapi.testclient import TestClient


def _setup(monkeypatch):
    # avoid network: stub embed + the model stream
    import app.chat.ingest as ingest
    import app.chat.retrieval as retrieval
    import app.chat.respond as respond
    monkeypatch.setattr(ingest, "_embed_sync", lambda t: [1.0, 0.0, 0.0])
    monkeypatch.setattr(retrieval, "_embed_sync", lambda t: [1.0, 0.0, 0.0])
    monkeypatch.setattr(respond.llm, "provider_supports_tools", lambda: True)

    async def fake_stream(messages, tools, **kw):
        yield {"type": "content_delta", "delta": "hi "}
        yield {"type": "content_delta", "delta": "there"}
        yield {"type": "done", "finish_reason": "stop",
               "message": {"role": "assistant", "content": "hi there"},
               "usage": {}, "duration_ms": 1}
    monkeypatch.setattr(respond.llm, "chat_with_tools_stream", fake_stream)


def test_chat_streams_and_persists_both_turns(migrated_db, monkeypatch):
    _setup(monkeypatch)
    from app.main import app
    from app.store import memory
    from app.store.traces import get_conn

    client = TestClient(app)
    with client.stream("POST", "/chat", json={"message": "hello"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "hi there" in body                     # streamed content reached client

    tail = memory.recent_tail(2)
    assert tail[0] == tail[0] and tail[0]["role"] == "user" and tail[0]["content"] == "hello"
    assert tail[1]["role"] == "assistant" and tail[1]["content"] == "hi there"

    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM traces WHERE stage='chat'").fetchone()["c"]
    assert n == 1                                  # one chat trace recorded
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chat_route.py -v`
Expected: FAIL — chat route not mounted (404) / import error.

- [ ] **Step 4: Create `api/app/routes/chat.py`**

```python
"""POST /chat — SSE stream. Persists the user turn, assembles context (A recall
baked in), streams the reply (B tool available), persists the assistant turn,
records one diagnostic trace."""
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.chat import assemble, ingest, respond
from app.llm.client import resolve_structured_llm_config
from app.store import traces

router = APIRouter()


class ChatIn(BaseModel):
    message: str


@router.post("/chat")
async def chat(body: ChatIn):
    ingest.persist_user(body.message)
    messages = assemble.build_messages(query=body.message)
    cfg = resolve_structured_llm_config()

    async def gen():
        final = ""
        async for ev in respond.stream(messages):
            if ev["type"] == "delta":
                yield f"data: {json.dumps({'delta': ev['text']}, ensure_ascii=False)}\n\n"
            elif ev["type"] == "final":
                final = ev["content"]
        ingest.persist_assistant(final)
        traces.record(
            turn=None, stage="chat", model=cfg.get("model"),
            params={"provider": cfg.get("provider")},
            prompt=json.dumps(messages, ensure_ascii=False), output=final,
            prompt_tokens=None, completion_tokens=None, duration_ms=None,
        )
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 5: Modify `api/app/main.py`** to mount the router

```python
from fastapi import FastAPI

from app.routes import chat as chat_routes

app = FastAPI(title="Vellum")
app.include_router(chat_routes.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run the integration test, then the full suite**

Run: `.venv/bin/python -m pytest tests/test_chat_route.py -v`
Expected: PASS
Run: `.venv/bin/python -m pytest -q`
Expected: all foundation + chat-loop tests pass.

- [ ] **Step 7: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: POST /chat SSE route + wiring + integration test"
```

---

## Done criteria

- `POST /chat {"message": "..."}` streams an SSE reply and persists both turns; one `traces` row per call.
- A retrieval is always baked into the assembled context (threshold-gated); B `recall_memory` is offered when the provider supports tools, else tools=[] (A-only) and it still streams.
- Altitude framing present in every system prompt.
- Personal model is READ only (dossier/facts/traits) — not yet updated. Updating is **Plan 3 (background modeling)**.
- Full test suite green.

---

## Self-Review

- **Spec coverage:** §7 consume loop steps 1–4 → Tasks 8 (persist user+embed), 6 (assemble), 9/10 (stream + persist assistant + trace). §7 召回 A (search-every-turn, threshold) → Tasks 1,4,6. §7 召回 B (recall_memory tool, multi-hop) → Tasks 7,9. §5 tool capability / degradation → Tasks 2,9. §3 altitude framing → Task 6 (`_ALTITUDE`). §6 "assistant not embedded, recalled via linkage" → Tasks 4 (hydrate window incl. assistant), 8 (assistant no embed). Trace (§6.4) → Task 10. NOT in scope (deferred): background modeling, evals harness, web — stated in Done criteria.
- **Placeholder scan:** none; every step has concrete code/commands/expected output. The one implementer-judgment note (anchor lookup helper in Task 4) offers two concrete acceptable implementations.
- **Type consistency:** `retrieval.retrieve(query,k,min_sim,w)->[{start,end,text}]` used identically by assemble (A), recall tool (B), and tests. `respond.stream(messages)` yields `{"type":"delta"|"final",...}` consumed identically by tests and the route. `ToolRegistry.register/schemas/dispatch`, `recall.register_into`, `ingest.persist_user/persist_assistant`, `provider_supports_tools`, `search_scored` consistent across definition and use. `_embed_sync` is the monkeypatch seam in both `retrieval` and `ingest`.
