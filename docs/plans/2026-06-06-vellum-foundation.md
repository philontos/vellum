# Vellum Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Vellum backend foundation — project scaffold, the pluggable LLM/embedding access layer (ported from engram), and the full storage layer (SQLite schema + migrations + DAOs + HNSW vector store) — all unit-tested.

**Architecture:** Single-user local FastAPI app. SQLite is the only home for text (`messages`, `summaries`, plus the personal-model and `traces` tables); an HNSW file is a separate search layer holding only embeddings + integer labels mapped back via `vector_refs`. DAO functions each open a short-lived connection through a `get_conn()` context manager. The LLM/embedding clients are ported near-verbatim from engram (universal OpenAI-compatible, env-configured).

**Tech Stack:** Python 3.12, FastAPI, uvicorn, httpx, sqlite3 (stdlib), hnswlib, numpy, pytest, pytest-asyncio.

**Source repo to port from:** `/Users/wangyuhao/Develop/personal/engram`

**Spec:** `docs/specs/2026-06-06-vellum-design.md` (§5 接入层, §6 存储模型).

---

## File Structure

```
vellum/
  api/
    app/
      __init__.py
      config.py            # env-driven paths (lazy, test-friendly)
      main.py              # FastAPI app + /health
      llm/
        __init__.py
        client.py          # PORTED from engram shared/llm/client.py
        embed.py           # PORTED from engram api/app/lib/embed.py
      store/
        __init__.py
        db.py              # connection ctx manager + migration runner
        vectors.py         # PORTED from engram vector_store.py + batch save
        memory.py          # messages / summaries / vector_refs / cursors DAO
        model.py           # dossier / trait_current / trait_history / facts DAO
        traces.py          # traces DAO (record / prune / pin)
    migrations/
      001_init.sql         # all tables
    tests/
      __init__.py
      conftest.py          # tmp data dir + migrated db fixture
      test_health.py
      test_db.py
      test_vectors.py
      test_memory.py
      test_model.py
      test_traces.py
      test_llm.py          # mocked httpx
    requirements.txt
    pytest.ini
    .env.example
  .gitignore
  AGENTS.md
```

**Responsibilities:** `config.py` resolves paths from env (lazy so tests can repoint). `store/db.py` owns connections + migrations only. Each DAO file owns exactly one storage concern. `llm/*` are leaf ports with no app deps. Tests mirror source 1:1.

All commands below are run from `/Users/wangyuhao/Develop/personal/vellum/api` unless stated. Use a venv:

```bash
cd /Users/wangyuhao/Develop/personal/vellum/api
python3.12 -m venv .venv && source .venv/bin/activate
```

---

## Task 1: Project scaffold + /health

**Files:**
- Create: `api/requirements.txt`, `api/pytest.ini`, `api/.env.example`, `.gitignore`, `AGENTS.md`
- Create: `api/app/__init__.py`, `api/app/config.py`, `api/app/main.py`
- Create: `api/tests/__init__.py`, `api/tests/conftest.py`, `api/tests/test_health.py`

- [ ] **Step 1: Create `.gitignore` (repo root)**

```
.venv/
__pycache__/
*.pyc
api/data/
.env
node_modules/
dist/
.DS_Store
```

- [ ] **Step 2: Create `api/requirements.txt`**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.28.1
hnswlib==0.8.0
numpy==2.2.1
pytest==8.3.4
pytest-asyncio==0.25.2
```

- [ ] **Step 3: Install**

Run: `pip install -r requirements.txt`
Expected: ends with `Successfully installed ...`

- [ ] **Step 4: Create `api/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 5: Create `api/.env.example`**

```bash
# Chat LLM (universal OpenAI-compatible). Either set LLM_PROVIDER preset + key,
# or set LLM_BASE_URL/LLM_API_KEY/LLM_MODEL explicitly.
LLM_PROVIDER=openai
LLM_API_KEY=
LLM_MODEL=gpt-4.1-mini

# Embedding. Falls back to LLM_* if unset. Pick a model strong in YOUR daily language.
EMBED_MODEL=text-embedding-3-small
# EMBED_BASE_URL=
# EMBED_API_KEY=

# Data location (sqlite db + vector index)
VELLUM_DATA_DIR=./data
```

- [ ] **Step 6: Create `api/app/__init__.py`** (empty file)

- [ ] **Step 7: Create `api/app/config.py`**

```python
"""Env-driven paths. Lazy (functions, not module constants) so tests repoint
VELLUM_DATA_DIR per-test without import-order pain."""
import os
from pathlib import Path


def data_dir() -> Path:
    return Path(os.getenv("VELLUM_DATA_DIR", "./data"))


def db_path() -> Path:
    return data_dir() / "vellum.db"


def vector_dir() -> Path:
    return data_dir() / "vectors"
```

- [ ] **Step 8: Write the failing test `api/tests/test_health.py`**

```python
from fastapi.testclient import TestClient
from app.main import app


def test_health_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 9: Create `api/tests/__init__.py`** (empty) and run test to verify it fails

Run: `python -m pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 10: Create `api/app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="Vellum")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 11: Run test to verify it passes**

Run: `python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 12: Create `api/tests/conftest.py`** (shared fixture used by later tasks)

```python
import pytest

from app.store import db


@pytest.fixture
def migrated_db(tmp_path, monkeypatch):
    """Point VELLUM_DATA_DIR at a tmp dir and run migrations. Yields nothing —
    DAOs open their own short-lived connections via config paths."""
    monkeypatch.setenv("VELLUM_DATA_DIR", str(tmp_path))
    db.run_migrations()
    yield tmp_path
```

- [ ] **Step 13: Create `AGENTS.md` (repo root)**

```markdown
# Vellum — repo rules for AI coding agents

- Single-user, local, data-isolated. No multi-user / accounts / SaaS.
- Text lives only in SQLite. The HNSW index holds embeddings + integer labels only.
- Canonical enums are English (`role`, `status`, `ref_type`, `concern`, dimension keys).
- Prompts default to English and instruct "match the user's language"; never pin output language.
- Migrations are forward-only and idempotent; never edit a committed migration, add a new one.
- TDD: write the failing test first. Small files, single responsibility.
- Design source of truth: `docs/specs/2026-06-06-vellum-design.md`.
```

- [ ] **Step 14: Commit**

```bash
cd /Users/wangyuhao/Develop/personal/vellum
git add -A
git commit -m "feat: project scaffold + /health endpoint"
```

---

## Task 2: DB connection + migration runner + schema

**Files:**
- Create: `api/app/store/__init__.py`, `api/app/store/db.py`
- Create: `api/migrations/001_init.sql`
- Test: `api/tests/test_db.py`

- [ ] **Step 1: Create `api/app/store/__init__.py`** (empty)

- [ ] **Step 2: Write the failing test `api/tests/test_db.py`**

```python
from app.store import db


def test_migrations_create_all_tables(migrated_db):
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    names = {r["name"] for r in rows}
    expected = {
        "messages", "summaries", "vector_refs", "cursors",
        "dossier", "trait_current", "trait_history", "facts", "traces",
        "schema_migrations",
    }
    assert expected <= names


def test_migrations_idempotent(migrated_db):
    # Running again must not raise and must not duplicate applied rows.
    db.run_migrations()
    with db.get_conn() as conn:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM schema_migrations WHERE name='001_init.sql'"
        ).fetchone()["c"]
    assert n == 1


def test_cursors_seeded(migrated_db):
    with db.get_conn() as conn:
        rows = conn.execute("SELECT concern FROM cursors").fetchall()
    assert {r["concern"] for r in rows} == {"facts", "trait", "summary", "dossier"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.store.db'`

- [ ] **Step 4: Create `api/app/store/db.py`**

```python
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import db_path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def _connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn():
    """Short-lived connection. Commits on clean exit, always closes."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def run_migrations() -> None:
    with get_conn() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            conn.executescript(path.read_text())
            conn.execute("INSERT INTO schema_migrations(name) VALUES (?)", (path.name,))
```

- [ ] **Step 5: Create `api/migrations/001_init.sql`**

```sql
-- Memory layer: global ordered stream
CREATE TABLE IF NOT EXISTS messages (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  turn        INTEGER NOT NULL UNIQUE,
  role        TEXT    NOT NULL CHECK (role IN ('user','assistant')),
  content     TEXT    NOT NULL,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_turn ON messages(turn);

CREATE TABLE IF NOT EXISTS summaries (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  start_turn  INTEGER NOT NULL,
  end_turn    INTEGER NOT NULL,
  content     TEXT    NOT NULL,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vector_refs (
  label       INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_type    TEXT    NOT NULL CHECK (ref_type IN ('message','summary')),
  ref_id      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cursors (
  concern       TEXT PRIMARY KEY CHECK (concern IN ('facts','trait','summary','dossier')),
  through_turn  INTEGER NOT NULL DEFAULT -1,
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO cursors(concern) VALUES ('facts'),('trait'),('summary'),('dossier');

-- Personal-model layer
CREATE TABLE IF NOT EXISTS dossier (
  id          INTEGER PRIMARY KEY CHECK (id = 1),
  content     TEXT    NOT NULL DEFAULT '',
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO dossier(id, content) VALUES (1, '');

CREATE TABLE IF NOT EXISTS trait_current (
  dimension     TEXT PRIMARY KEY,
  content_json  TEXT    NOT NULL,
  sample_count  INTEGER NOT NULL DEFAULT 0,
  updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS trait_history (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  dimension     TEXT    NOT NULL,
  content_json  TEXT    NOT NULL,
  taken_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trait_history_dim ON trait_history(dimension, taken_at);

CREATE TABLE IF NOT EXISTS facts (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  text        TEXT    NOT NULL,
  status      TEXT    NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded')),
  source_turn INTEGER,
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);

-- Observability layer
CREATE TABLE IF NOT EXISTS traces (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  turn               INTEGER,
  stage              TEXT    NOT NULL,
  model              TEXT,
  params             TEXT,
  prompt             TEXT,
  output             TEXT,
  prompt_tokens      INTEGER,
  completion_tokens  INTEGER,
  duration_ms        INTEGER,
  pinned             INTEGER NOT NULL DEFAULT 0,
  created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_traces_created ON traces(created_at);
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_db.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
cd /Users/wangyuhao/Develop/personal/vellum
git add -A
git commit -m "feat: sqlite schema + idempotent migration runner"
```

---

## Task 3: Vector store (port HNSW wrapper + batch save)

**Files:**
- Create: `api/app/store/vectors.py` (port of engram `api/app/lib/vector_store.py`)
- Test: `api/tests/test_vectors.py`

- [ ] **Step 1: Write the failing test `api/tests/test_vectors.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vectors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.store.vectors'`

- [ ] **Step 3: Create `api/app/store/vectors.py`**

Port of engram's `api/app/lib/vector_store.py`. Change from engram: read the index path from `app.config.vector_dir()` (not an env var), and add an explicit `save()` instead of saving on every `add` (batch-friendly; callers save once after a batch).

```python
"""HNSW vector index. Holds embeddings + integer labels ONLY (no text).
Labels map back to source rows via the `vector_refs` table (see store.memory)."""
from pathlib import Path

import hnswlib
import numpy as np

from app.config import vector_dir

MAX_ELEMENTS = 1_000_000


class VectorStore:
    def __init__(self):
        d = vector_dir()
        d.mkdir(parents=True, exist_ok=True)
        self._index_path = d / "index.bin"
        self._dim_file = d / "dim.txt"
        self.index: hnswlib.Index | None = None
        self.dim: int | None = None
        if self._dim_file.exists():
            self.dim = int(self._dim_file.read_text().strip())
            self._load_or_init()

    def _load_or_init(self):
        self.index = hnswlib.Index(space="cosine", dim=self.dim)
        if self._index_path.exists():
            self.index.load_index(str(self._index_path), max_elements=MAX_ELEMENTS)
        else:
            self.index.init_index(max_elements=MAX_ELEMENTS, ef_construction=200, M=16)
        self.index.set_ef(64)

    def add(self, label: int, embedding: list[float], *, save: bool = True):
        if self.dim is None:
            self.dim = len(embedding)
            self._dim_file.write_text(str(self.dim))
            self._load_or_init()
        self.index.add_items(
            np.array([embedding], dtype=np.float32),
            np.array([label]),
        )
        if save:
            self.save()

    def save(self):
        if self.index is not None:
            self.index.save_index(str(self._index_path))

    def search(self, embedding: list[float], k: int = 5) -> list[int]:
        if self.index is None or self.index.get_current_count() == 0:
            return []
        labels, _ = self.index.knn_query(
            np.array([embedding], dtype=np.float32),
            k=min(k, self.index.get_current_count()),
        )
        return labels[0].tolist()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_vectors.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/wangyuhao/Develop/personal/vellum
git add -A
git commit -m "feat: HNSW vector store (ported, explicit batch save)"
```

---

## Task 4: Memory DAO (messages / summaries / vector_refs / cursors)

**Files:**
- Create: `api/app/store/memory.py`
- Test: `api/tests/test_memory.py`

- [ ] **Step 1: Write the failing test `api/tests/test_memory.py`**

```python
from app.store import memory


def test_append_message_assigns_monotonic_turns(migrated_db):
    a = memory.append_message("user", "hi")
    b = memory.append_message("assistant", "hello")
    c = memory.append_message("user", "how are you")
    assert (a["turn"], b["turn"], c["turn"]) == (0, 1, 2)


def test_recent_tail_returns_last_n_in_order(migrated_db):
    for i in range(5):
        memory.append_message("user", f"m{i}")
    tail = memory.recent_tail(limit=3)
    assert [m["content"] for m in tail] == ["m2", "m3", "m4"]


def test_messages_in_turn_range_inclusive(migrated_db):
    for i in range(5):
        memory.append_message("user", f"m{i}")
    rows = memory.messages_in_turn_range(1, 3)
    assert [m["turn"] for m in rows] == [1, 2, 3]


def test_summary_add_and_get(migrated_db):
    sid = memory.add_summary(0, 4, "discussed the offer")
    s = memory.get_summary(sid)
    assert s["start_turn"] == 0 and s["end_turn"] == 4
    assert s["content"] == "discussed the offer"


def test_vector_ref_roundtrip(migrated_db):
    label = memory.add_vector_ref("message", 42)
    ref = memory.resolve_vector_ref(label)
    assert ref == {"ref_type": "message", "ref_id": 42}


def test_cursor_get_and_advance(migrated_db):
    assert memory.get_cursor("trait") == -1
    memory.advance_cursor("trait", 9)
    assert memory.get_cursor("trait") == 9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.store.memory'`

- [ ] **Step 3: Create `api/app/store/memory.py`**

```python
"""Memory layer DAO: the global message stream, conversation summaries,
HNSW label->source mapping, and per-concern modeling cursors."""
from app.store.db import get_conn


def append_message(role: str, content: str) -> dict:
    """Append to the single eternal stream; assign the next global turn."""
    with get_conn() as conn:
        turn = conn.execute(
            "SELECT COALESCE(MAX(turn), -1) + 1 AS t FROM messages"
        ).fetchone()["t"]
        cur = conn.execute(
            "INSERT INTO messages(turn, role, content) VALUES (?, ?, ?)",
            (turn, role, content),
        )
        return {"id": cur.lastrowid, "turn": turn}


def recent_tail(limit: int) -> list[dict]:
    """Most recent `limit` messages, returned oldest->newest."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages ORDER BY turn DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def messages_in_turn_range(start_turn: int, end_turn: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE turn BETWEEN ? AND ? ORDER BY turn",
            (start_turn, end_turn),
        ).fetchall()
    return [dict(r) for r in rows]


def max_turn() -> int:
    with get_conn() as conn:
        return conn.execute(
            "SELECT COALESCE(MAX(turn), -1) AS t FROM messages"
        ).fetchone()["t"]


def add_summary(start_turn: int, end_turn: int, content: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO summaries(start_turn, end_turn, content) VALUES (?, ?, ?)",
            (start_turn, end_turn, content),
        )
        return cur.lastrowid


def get_summary(summary_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,)).fetchone()
    return dict(row) if row else None


def add_vector_ref(ref_type: str, ref_id: int) -> int:
    """Allocate an HNSW label bound to a source row. Returns the label."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO vector_refs(ref_type, ref_id) VALUES (?, ?)",
            (ref_type, ref_id),
        )
        return cur.lastrowid


def resolve_vector_ref(label: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ref_type, ref_id FROM vector_refs WHERE label = ?", (label,)
        ).fetchone()
    return dict(row) if row else None


def get_cursor(concern: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT through_turn FROM cursors WHERE concern = ?", (concern,)
        ).fetchone()
    return row["through_turn"] if row else -1


def advance_cursor(concern: str, through_turn: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE cursors SET through_turn = ?, updated_at = datetime('now') "
            "WHERE concern = ?",
            (through_turn, concern),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_memory.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/wangyuhao/Develop/personal/vellum
git add -A
git commit -m "feat: memory DAO (stream, summaries, vector_refs, cursors)"
```

---

## Task 5: Model DAO (dossier / trait_current+history / facts)

**Files:**
- Create: `api/app/store/model.py`
- Test: `api/tests/test_model.py`

- [ ] **Step 1: Write the failing test `api/tests/test_model.py`**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.store.model'`

- [ ] **Step 3: Create `api/app/store/model.py`**

```python
"""Personal-model DAO: dossier (one row), trait_current (live, overwritten) +
trait_history (append-only snapshot), and facts (pin board with lifecycle).

Note: trait snapshotting is 'archive-on-create' — set_trait writes the live row
AND immediately appends the same value to history, so the latest value is never
lost even if no further update ever happens."""
import json

from app.store.db import get_conn


def get_dossier() -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT content FROM dossier WHERE id = 1").fetchone()
    return row["content"] if row else ""


def set_dossier(content: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE dossier SET content = ?, updated_at = datetime('now') WHERE id = 1",
            (content,),
        )


def set_trait(dimension: str, content: dict, sample_count: int) -> None:
    blob = json.dumps(content, ensure_ascii=False)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO trait_current(dimension, content_json, sample_count) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(dimension) DO UPDATE SET "
            "content_json = excluded.content_json, "
            "sample_count = excluded.sample_count, updated_at = datetime('now')",
            (dimension, blob, sample_count),
        )
        # archive-on-create: freeze a snapshot the moment this value becomes current
        conn.execute(
            "INSERT INTO trait_history(dimension, content_json) VALUES (?, ?)",
            (dimension, blob),
        )


def get_trait(dimension: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM trait_current WHERE dimension = ?", (dimension,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["content_json"] = json.loads(d["content_json"])
    return d


def get_trait_history(dimension: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trait_history WHERE dimension = ? ORDER BY id", (dimension,)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["content_json"] = json.loads(d["content_json"])
        out.append(d)
    return out


def add_fact(text: str, source_turn: int | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO facts(text, source_turn) VALUES (?, ?)", (text, source_turn)
        )
        return cur.lastrowid


def active_facts() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM facts WHERE status = 'active' ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def supersede_fact(fact_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE facts SET status = 'superseded', updated_at = datetime('now') "
            "WHERE id = ?",
            (fact_id,),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_model.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/wangyuhao/Develop/personal/vellum
git add -A
git commit -m "feat: personal-model DAO (dossier, traits+history, facts)"
```

---

## Task 6: Traces DAO (record / prune / pin)

**Files:**
- Create: `api/app/store/traces.py`
- Test: `api/tests/test_traces.py`

- [ ] **Step 1: Write the failing test `api/tests/test_traces.py`**

```python
from app.store import traces
from app.store.db import get_conn


def _record(stage="chat", pinned=False):
    return traces.record(
        turn=1, stage=stage, model="m", params={"t": 0.7},
        prompt="big prompt", output="big output",
        prompt_tokens=10, completion_tokens=20, duration_ms=5, pinned=pinned,
    )


def test_record_persists_full_fields(migrated_db):
    tid = _record()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row["prompt"] == "big prompt" and row["output"] == "big output"
    assert row["completion_tokens"] == 20


def test_prune_nulls_heavy_fields_keeps_row_and_metadata(migrated_db):
    tid = _record()
    traces.prune(keep_last=0)            # prune everything eligible
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row is not None               # row survives
    assert row["prompt"] is None and row["output"] is None   # heavy fields cleared
    assert row["prompt_tokens"] == 10    # metadata kept


def test_prune_spares_pinned(migrated_db):
    tid = _record(pinned=True)
    traces.prune(keep_last=0)
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM traces WHERE id = ?", (tid,)).fetchone()
    assert row["prompt"] == "big prompt"  # pinned heavy fields untouched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_traces.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.store.traces'`

- [ ] **Step 3: Create `api/app/store/traces.py`**

```python
"""Observability DAO: raw LLM-call traces. Diagnostic exhaust — not memory,
not retrieved, not modeled. Retention = rolling window of heavy fields
(prompt/output) + forever-metadata; prune nulls heavy fields but keeps the row;
pinned rows are spared."""
import json

from app.store.db import get_conn


def record(*, turn, stage, model, params, prompt, output,
           prompt_tokens, completion_tokens, duration_ms, pinned=False) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO traces(turn, stage, model, params, prompt, output, "
            "prompt_tokens, completion_tokens, duration_ms, pinned) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (turn, stage, model, json.dumps(params, ensure_ascii=False),
             prompt, output, prompt_tokens, completion_tokens, duration_ms,
             1 if pinned else 0),
        )
        return cur.lastrowid


def prune(keep_last: int) -> None:
    """Null out prompt/output on all but the most recent `keep_last` unpinned
    rows. Rows (and their lightweight metadata) are always kept."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE traces SET prompt = NULL, output = NULL "
            "WHERE pinned = 0 AND prompt IS NOT NULL AND id NOT IN ("
            "  SELECT id FROM traces WHERE pinned = 0 ORDER BY id DESC LIMIT ?"
            ")",
            (keep_last,),
        )


def pin(trace_id: int, pinned: bool = True) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE traces SET pinned = ? WHERE id = ?",
            (1 if pinned else 0, trace_id),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_traces.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/wangyuhao/Develop/personal/vellum
git add -A
git commit -m "feat: traces DAO (record, rolling prune, pin)"
```

---

## Task 7: Port LLM client + embedding access layer

**Files:**
- Create: `api/app/llm/__init__.py`, `api/app/llm/client.py`, `api/app/llm/embed.py`
- Test: `api/tests/test_llm.py`

Port engram's proven, self-contained clients near-verbatim. They have no app
dependencies, so the port is a copy + an import-path sanity check.

- [ ] **Step 1: Copy the two files from engram**

Run:
```bash
mkdir -p /Users/wangyuhao/Develop/personal/vellum/api/app/llm
touch /Users/wangyuhao/Develop/personal/vellum/api/app/llm/__init__.py
cp /Users/wangyuhao/Develop/personal/engram/shared/llm/client.py \
   /Users/wangyuhao/Develop/personal/vellum/api/app/llm/client.py
cp /Users/wangyuhao/Develop/personal/engram/api/app/lib/embed.py \
   /Users/wangyuhao/Develop/personal/vellum/api/app/llm/embed.py
```

- [ ] **Step 2: Verify the ports import cleanly (no app-internal imports)**

Run: `python -c "import app.llm.client, app.llm.embed; print('ok')"`
Expected: `ok` (if it fails with an `app.*` import error, delete that import — these
files must stay leaf modules; report any such line before changing behavior).

- [ ] **Step 3: Write the failing test `api/tests/test_llm.py`** (mock httpx; no network)

```python
import httpx
import pytest

from app.llm import client as llm
from app.llm import embed as emb


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_chat_json_parses_object(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "gpt-4.1-mini")

    async def fake_post(self, url, headers=None, json=None):
        return _Resp(200, {"choices": [{"message": {"content": '{"ok": true}'}}],
                           "usage": {}})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    out = await llm.chat_json(system_prompt="x", user_prompt="y")
    assert out == {"ok": True}


@pytest.mark.asyncio
async def test_embed_returns_vector(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("EMBED_MODEL", "text-embedding-3-small")

    async def fake_post(self, url, headers=None, json=None):
        return _Resp(200, {"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    vec = await emb.embed("hello")
    assert vec == [0.1, 0.2, 0.3]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_llm.py -v`
Expected: 2 passed

(If `chat_json` signature differs in the engram copy, align the test call to the
real signature — do not change the ported client's behavior.)

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -v`
Expected: all tests from Tasks 1-7 pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/wangyuhao/Develop/personal/vellum
git add -A
git commit -m "feat: port pluggable LLM client + embedding layer from engram"
```

---

## Done criteria for this plan

- `python -m pytest -v` is green from `api/`.
- `uvicorn app.main:app` serves `/health` → `{"status":"ok"}`.
- All storage tables exist via idempotent migration; DAOs for memory / model / traces are tested.
- Vector store add/search/persist works; labels resolve to sources via `vector_refs`.
- LLM chat + embedding clients are ported and exercised (mocked).

This foundation is consumed by **Plan 2 (chat consume loop)**, which assembles
context (dossier + active facts + trait summary + A-retrieval + tail), streams a
reply, and adds the B `recall_memory` tool.

---

## Self-Review

- **Spec coverage (Plan 1 portion):** §5 接入层 → Task 7. §6.2 记忆层 (messages/summaries/vector_refs/cursors) → Tasks 2,4. §6.3 个人模型层 (dossier/trait_current/trait_history/facts) → Tasks 2,5. §6.4 traces → Tasks 2,6. ② HNSW + label→source mapping → Tasks 3,4. §10 栈/目录/迁移约定 → Tasks 1,2. Consume loop / modeling / evals / web are explicitly deferred to Plans 2-5.
- **Placeholder scan:** none — every step has concrete code/commands/expected output.
- **Type consistency:** `add_vector_ref`/`resolve_vector_ref`, `get_cursor`/`advance_cursor`, `set_trait`/`get_trait`/`get_trait_history`, `add_fact`/`active_facts`/`supersede_fact`, `traces.record`/`prune`/`pin` are used consistently between source and tests. `get_conn()` is a context manager everywhere. `VectorStore.add(label, embedding, save=)` / `.search()` / `.save()` consistent across Task 3 and downstream.
