# Vellum Inspection Panels Implementation Plan (Phase 1: visualize model + traces)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** See the personal model (dossier / facts / trait dimensions + evolution curves) and **every pipeline LLM call as a trace** (chat + facts + trait + summary + dossier), with full prompt/output, filter-by-stage, and pin/note (pinned traces survive the rolling prune). Read-only except pin/note. (Trace-based `replay` eval is a later phase — out of scope here.)

**Architecture:** Builds on `main`. Backend: a migration adds `traces.note`; the background-modeling runner wraps each job in the client's existing `capture_llm_calls` sink and flushes the captured calls into the `traces` table (chat already records its own trace); read-only `/inspect/*` endpoints expose the model + traces. Frontend: the chat SPA gains top-nav views — **Chat / 你是谁 (model) / Traces** — with dependency-free SVG for trait bars + history curves.

**Tech Stack:** Same. Frontend: existing React/Vite/TS/Tailwind; charts hand-rolled SVG (no new deps).

**Depends on (`main`):** `app.store.{traces,model,memory,db}`, `app.model_loop.runner`, `app.llm.client.capture_llm_calls`, the web app + `client.ts`/nav.

Backend cmds from `api/` (`.venv/bin/python`); frontend from `web/`.

---

## Task 1: Migration + DAO additions

**Files:** Create `api/migrations/002_traces_note.sql`; modify `api/app/store/traces.py`, `api/app/store/model.py`; Test `api/tests/test_inspect_dao.py`

- [ ] **Step 1: Create `api/migrations/002_traces_note.sql`**

```sql
ALTER TABLE traces ADD COLUMN note TEXT;
```

- [ ] **Step 2: Write the failing test `api/tests/test_inspect_dao.py`**

```python
from app.store import traces, model
from app.store.db import get_conn


def _rec(stage="trait"):
    return traces.record(turn=1, stage=stage, model="m", params={}, prompt="p",
                         output="o", prompt_tokens=1, completion_tokens=2, duration_ms=3)


def test_note_column_exists_and_settable(migrated_db):
    tid = _rec()
    traces.set_note(tid, "wrong fact")
    with get_conn() as conn:
        row = conn.execute("SELECT note FROM traces WHERE id=?", (tid,)).fetchone()
    assert row["note"] == "wrong fact"


def test_list_recent_filters_by_stage(migrated_db):
    _rec("facts"); _rec("trait"); _rec("facts")
    allrows = traces.list_recent(limit=10)
    factrows = traces.list_recent(limit=10, stage="facts")
    assert len(allrows) == 3 and len(factrows) == 2
    assert allrows[0]["id"] > allrows[-1]["id"]      # newest first


def test_all_facts_and_traits(migrated_db):
    model.add_fact("f1"); fid = model.add_fact("f2"); model.supersede_fact(fid)
    assert {f["text"] for f in model.all_facts()} == {"f1", "f2"}
    model.set_trait("ocean", {"O": {"score": 70}}, 1)
    rows = model.all_traits()
    assert rows[0]["dimension"] == "ocean" and rows[0]["content_json"]["O"]["score"] == 70
```

- [ ] **Step 3: Run test → fails**

Run: `.venv/bin/python -m pytest tests/test_inspect_dao.py -v`
Expected: FAIL (`set_note`/`list_recent`/`all_facts`/`all_traits` missing; note column missing).

- [ ] **Step 4: Add to `api/app/store/traces.py`**

```python
def list_recent(limit: int = 100, stage: str | None = None) -> list[dict]:
    with get_conn() as conn:
        if stage:
            rows = conn.execute(
                "SELECT * FROM traces WHERE stage = ? ORDER BY id DESC LIMIT ?",
                (stage, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM traces ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def set_note(trace_id: int, note: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE traces SET note = ? WHERE id = ?", (note, trace_id))
```

- [ ] **Step 5: Add to `api/app/store/model.py`**

```python
def all_facts() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM facts ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def all_traits() -> list[dict]:
    with get_conn() as conn:
        dims = [r["dimension"] for r in
                conn.execute("SELECT dimension FROM trait_current ORDER BY dimension")]
    return [get_trait(d) for d in dims]


def get_dossier_row() -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT content, updated_at FROM dossier WHERE id = 1").fetchone()
    return dict(row) if row else {"content": "", "updated_at": None}
```

- [ ] **Step 6: Run tests → pass**

Run: `.venv/bin/python -m pytest tests/test_inspect_dao.py -v`
Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(inspect): traces.note migration + list_recent/set_note + model.all_facts/all_traits"
```

---

## Task 2: Trace every modeling LLM call

**Files:** Modify `api/app/model_loop/runner.py`; Test `api/tests/test_model_trace_flush.py`

The client already records each call (stage/model/full prompt/output/tokens/duration) into a `capture_llm_calls` sink when one is active. Wrap each job and flush the sink to `traces` — including failed calls (their error body is useful for tuning).

- [ ] **Step 1: Write the failing test `api/tests/test_model_trace_flush.py`**

```python
import pytest

from app.model_loop import runner
from app.store import traces


def test_flush_writes_one_trace_per_captured_call(migrated_db):
    calls = [
        {"stage": "trait", "model": "m", "status": "ok", "system_prompt": "SYS",
         "user_prompt": "U", "response": "RESP", "prompt_tokens": 5,
         "completion_tokens": 6, "duration_ms": 7},
        {"stage": "facts", "model": "m", "status": "http_error", "error": "boom",
         "system_prompt": "S2", "user_prompt": "", "response": "errbody",
         "prompt_tokens": 0, "completion_tokens": 0, "duration_ms": 1},
    ]
    runner._flush_traces(calls, turn=4)
    rows = traces.list_recent(limit=10)
    assert {r["stage"] for r in rows} == {"trait", "facts"}
    trait_row = next(r for r in rows if r["stage"] == "trait")
    assert "SYS" in trait_row["prompt"] and trait_row["output"] == "RESP"
    assert trait_row["completion_tokens"] == 6


@pytest.mark.asyncio
async def test_run_concern_flushes_job_calls(migrated_db, monkeypatch):
    from app.llm.client import capture_llm_calls

    async def fake_job(start, end):
        # simulate the client recording a call mid-job
        from app.llm.client import _record_llm_call
        _record_llm_call({"stage": "dossier", "model": "m", "status": "ok",
                          "system_prompt": "P", "user_prompt": "", "response": "D",
                          "prompt_tokens": 1, "completion_tokens": 1, "duration_ms": 1})

    monkeypatch.setattr(runner.config, "dossier_batch_m", lambda: 1)
    # only run the dossier concern by giving the others a no-op
    async def noop(s, e): pass
    monkeypatch.setattr(runner.facts, "run", noop)
    monkeypatch.setattr(runner.traits, "run", noop)
    monkeypatch.setattr(runner.summary, "run", noop)
    monkeypatch.setattr(runner.dossier, "run", fake_job)
    from app.store import memory
    memory.append_message("user", "x")
    await runner.run_pending()
    assert any(r["stage"] == "dossier" and r["output"] == "D"
               for r in traces.list_recent(limit=10))
```

- [ ] **Step 2: Run test → fails**

Run: `.venv/bin/python -m pytest tests/test_model_trace_flush.py -v`
Expected: FAIL (`runner._flush_traces` missing).

- [ ] **Step 3: Modify `api/app/model_loop/runner.py`** — add imports and the flush; wrap the job in `_run_concern`.

Add imports near the top:
```python
from app.llm.client import capture_llm_calls
from app.store import traces
```

Add the flush helper (module level):
```python
def _flush_traces(calls: list[dict], turn: int) -> None:
    """Persist captured LLM calls (success or failure) as trace rows."""
    for c in calls:
        prompt = (c.get("system_prompt") or "")
        if c.get("user_prompt"):
            prompt += "\n\n[user]\n" + c["user_prompt"]
        traces.record(
            turn=turn,
            stage=c.get("stage") or "?",
            model=c.get("model"),
            params={"status": c.get("status"), "error": c.get("error")},
            prompt=prompt,
            output=c.get("response") or "",
            prompt_tokens=c.get("prompt_tokens"),
            completion_tokens=c.get("completion_tokens"),
            duration_ms=c.get("duration_ms"),
        )
```

Rewrite `_run_concern` to capture + flush (capture even on failure):
```python
async def _run_concern(concern: str, job, gap_threshold: int, max_turn: int) -> None:
    cursor = memory.get_cursor(concern)
    if max_turn - cursor < gap_threshold:
        return
    calls: list[dict] = []
    try:
        with capture_llm_calls(calls):
            await job(cursor + 1, max_turn)
        memory.advance_cursor(concern, max_turn)
    except Exception as exc:
        import traceback
        print(f"[model_loop] {concern} job failed: {exc!r}", flush=True)
        traceback.print_exc()
    finally:
        _flush_traces(calls, max_turn)
```

- [ ] **Step 4: Run tests → pass**

Run: `.venv/bin/python -m pytest tests/test_model_trace_flush.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(inspect): capture every modeling LLM call (facts/trait/summary/dossier) as a trace"
```

---

## Task 3: Read-only inspect endpoints

**Files:** Create `api/app/routes/inspect.py`; modify `api/app/main.py`, `web/vite.config.ts`; Test `api/tests/test_inspect_routes.py`

- [ ] **Step 1: Write the failing test `api/tests/test_inspect_routes.py`**

```python
from fastapi.testclient import TestClient


def test_inspect_model_and_traces(migrated_db):
    from app.main import app
    from app.store import model, traces
    model.set_dossier("who you are")
    model.add_fact("allergic to penicillin")
    model.set_trait("ocean", {"O": {"score": 72}}, 1)
    tid = traces.record(turn=1, stage="trait", model="m", params={}, prompt="p",
                        output="o", prompt_tokens=1, completion_tokens=1, duration_ms=1)

    c = TestClient(app)
    m = c.get("/inspect/model").json()
    assert m["dossier"] == "who you are"
    assert any(f["text"] == "allergic to penicillin" for f in m["facts"])
    assert m["traits"][0]["dimension"] == "ocean"
    assert "history" in m["traits"][0]

    t = c.get("/inspect/traces?stage=trait").json()["traces"]
    assert t[0]["id"] == tid and t[0]["stage"] == "trait"

    r = c.post(f"/inspect/traces/{tid}", json={"pinned": True, "note": "good"})
    assert r.status_code == 200
    row = c.get("/inspect/traces").json()["traces"][0]
    assert row["pinned"] == 1 and row["note"] == "good"
```

- [ ] **Step 2: Run test → fails**

Run: `.venv/bin/python -m pytest tests/test_inspect_routes.py -v`
Expected: FAIL (routes 404).

- [ ] **Step 3: Create `api/app/routes/inspect.py`**

```python
"""Read-only inspection of the personal model + diagnostic traces (plus pin/note
on traces). For the web inspection panels — not part of the chat hot path."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.store import model, traces

router = APIRouter()


@router.get("/inspect/model")
def inspect_model():
    traits = model.all_traits()
    for t in traits:
        t["history"] = model.get_trait_history(t["dimension"])
    return {
        "dossier": model.get_dossier(),
        "dossier_meta": model.get_dossier_row(),
        "facts": model.all_facts(),
        "traits": traits,
    }


@router.get("/inspect/traces")
def inspect_traces(limit: int = 100, stage: str | None = None):
    return {"traces": traces.list_recent(limit=limit, stage=stage)}


class TracePatch(BaseModel):
    pinned: bool | None = None
    note: str | None = None


@router.post("/inspect/traces/{trace_id}")
def patch_trace(trace_id: int, body: TracePatch):
    if body.pinned is not None:
        traces.pin(trace_id, body.pinned)
    if body.note is not None:
        traces.set_note(trace_id, body.note)
    return {"ok": True}
```

- [ ] **Step 4: Mount in `api/app/main.py`** — add import + include:

```python
from app.routes import inspect as inspect_routes
...
app.include_router(inspect_routes.router)
```

- [ ] **Step 5: Add `/inspect` to the Vite proxy** in `web/vite.config.ts` `server.proxy`:

```ts
      "/inspect": "http://localhost:18080",
```

- [ ] **Step 6: Run tests + full suite → pass**

Run: `.venv/bin/python -m pytest tests/test_inspect_routes.py -v` (PASS) then `.venv/bin/python -m pytest -q` (all green).

- [ ] **Step 7: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat(inspect): read-only /inspect/model + /inspect/traces + pin/note endpoint"
```

---

## Task 4: Frontend — API client additions

**Files:** Modify `web/src/api/client.ts`

- [ ] **Step 1: Append to `web/src/api/client.ts`**

```ts
export type TraitDim = {
  dimension: string;
  content_json: Record<string, { score?: number; confidence?: number; evidence?: string }>;
  sample_count: number;
  updated_at: string;
  history: { taken_at: string; content_json: Record<string, { score?: number }> }[];
};
export type Fact = { id: number; text: string; status: string; source_turn: number | null };
export type ModelView = { dossier: string; facts: Fact[]; traits: TraitDim[] };
export type Trace = {
  id: number; turn: number | null; stage: string; model: string | null;
  prompt: string | null; output: string | null; prompt_tokens: number | null;
  completion_tokens: number | null; duration_ms: number | null; pinned: number;
  note: string | null; created_at: string;
};

export async function getModel(): Promise<ModelView> {
  const r = await fetch("/inspect/model");
  if (!r.ok) throw new Error(`model failed: ${r.status}`);
  return r.json();
}

export async function getTraces(stage?: string, limit = 100): Promise<Trace[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (stage) q.set("stage", stage);
  const r = await fetch(`/inspect/traces?${q}`);
  if (!r.ok) throw new Error(`traces failed: ${r.status}`);
  return (await r.json()).traces;
}

export async function patchTrace(id: number, patch: { pinned?: boolean; note?: string }): Promise<void> {
  const r = await fetch(`/inspect/traces/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`patch failed: ${r.status}`);
}
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum add web && git -C /Users/wangyuhao/Develop/personal/vellum commit -m "feat(web): inspect API client (model/traces/patch)"
```

---

## Task 5: Frontend — nav shell + Model panel

**Files:** Modify `web/src/App.tsx`; create `web/src/components/ModelPanel.tsx`, `web/src/components/TraitChart.tsx`

- [ ] **Step 1: Create `web/src/components/TraitChart.tsx`** (dependency-free SVG: bars now + history lines)

```tsx
import type { TraitDim } from "../api/client";

const W = 280, H = 90, PAD = 6;

export function TraitChart({ dim }: { dim: TraitDim }) {
  const subs = Object.entries(dim.content_json)
    .filter(([, v]) => typeof v?.score === "number")
    .map(([k, v]) => [k, v.score as number] as const);

  // history → one polyline per sub-dimension (score 0..100)
  const pts = dim.history.length;
  const x = (i: number) => PAD + (pts <= 1 ? 0 : (i * (W - 2 * PAD)) / (pts - 1));
  const y = (score: number) => H - PAD - (score / 100) * (H - 2 * PAD);
  const colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2"];

  return (
    <div className="rounded-xl border border-gray-200 p-3">
      <div className="mb-2 text-sm font-semibold">{dim.dimension}</div>
      {subs.map(([k, score], i) => (
        <div key={k} className="mb-1 flex items-center gap-2 text-xs">
          <span className="w-6 text-gray-500">{k}</span>
          <div className="h-2 flex-1 rounded bg-gray-100">
            <div className="h-2 rounded" style={{ width: `${score}%`, background: colors[i % colors.length] }} />
          </div>
          <span className="w-8 text-right tabular-nums">{Math.round(score)}</span>
        </div>
      ))}
      {pts > 1 && (
        <svg width={W} height={H} className="mt-2 w-full">
          {subs.map(([k], i) => {
            const path = dim.history
              .map((h, idx) => `${idx ? "L" : "M"}${x(idx)},${y(h.content_json[k]?.score ?? 50)}`)
              .join(" ");
            return <path key={k} d={path} fill="none" stroke={colors[i % colors.length]} strokeWidth="1.5" />;
          })}
        </svg>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `web/src/components/ModelPanel.tsx`**

```tsx
import { useEffect, useState } from "react";
import { getModel, type ModelView } from "../api/client";
import { TraitChart } from "./TraitChart";

export function ModelPanel() {
  const [m, setM] = useState<ModelView | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    getModel().then(setM).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <div className="p-4 text-sm text-red-600">{err}</div>;
  if (!m) return <div className="p-4 text-sm text-gray-400">加载中…</div>;

  const activeFacts = m.facts.filter((f) => f.status === "active");
  const oldFacts = m.facts.filter((f) => f.status !== "active");

  return (
    <div className="space-y-5 overflow-y-auto p-4">
      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">Dossier — 你是谁</h2>
        <div className="whitespace-pre-wrap rounded-xl bg-gray-50 p-3 text-sm">
          {m.dossier || <span className="text-gray-400">（还没生成）</span>}
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">Facts</h2>
        <ul className="space-y-1 text-sm">
          {activeFacts.map((f) => <li key={f.id}>• {f.text}</li>)}
          {oldFacts.map((f) => <li key={f.id} className="text-gray-400 line-through">• {f.text}</li>)}
          {m.facts.length === 0 && <li className="text-gray-400">（还没抽到事实）</li>}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-gray-700">人格维度</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {m.traits.map((d) => <TraitChart key={d.dimension} dim={d} />)}
          {m.traits.length === 0 && <div className="text-sm text-gray-400">（还没建模，多聊几轮）</div>}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 3: Rewrite `web/src/App.tsx`** as a nav shell

```tsx
import { useState } from "react";
import { MessageList } from "./components/MessageList";
import { Composer } from "./components/Composer";
import { ModelPanel } from "./components/ModelPanel";
import { TracesPanel } from "./components/TracesPanel";
import { useChat } from "./hooks/useChat";

type View = "chat" | "model" | "traces";

export default function App() {
  const [view, setView] = useState<View>("chat");
  const { messages, streaming, send } = useChat();

  const tab = (v: View, label: string) => (
    <button
      onClick={() => setView(v)}
      className={`px-3 py-2 text-sm ${view === v ? "border-b-2 border-blue-600 font-medium" : "text-gray-500"}`}
    >
      {label}
    </button>
  );

  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col">
      <header className="flex items-center gap-1 border-b border-gray-200 px-2">
        <span className="px-2 text-sm font-semibold text-gray-700">Vellum</span>
        {tab("chat", "聊天")}
        {tab("model", "你是谁")}
        {tab("traces", "Traces")}
      </header>
      {view === "chat" && (
        <>
          <MessageList messages={messages} />
          <Composer onSend={send} disabled={streaming} />
        </>
      )}
      {view === "model" && <ModelPanel />}
      {view === "traces" && <TracesPanel />}
    </div>
  );
}
```

- [ ] **Step 4: Commit** (TracesPanel comes in Task 6 — create a temporary stub so the build passes if you build now, or commit together with Task 6)

```bash
git -C /Users/wangyuhao/Develop/personal/vellum add web && git -C /Users/wangyuhao/Develop/personal/vellum commit -m "feat(web): nav shell + model panel (dossier/facts/trait bars+curves)"
```

> Note: `App.tsx` imports `TracesPanel`, created in Task 6. Implement Task 6 before running `pnpm build`.

---

## Task 6: Frontend — Traces panel

**Files:** Create `web/src/components/TracesPanel.tsx`

- [ ] **Step 1: Create `web/src/components/TracesPanel.tsx`**

```tsx
import { useEffect, useState } from "react";
import { getTraces, patchTrace, type Trace } from "../api/client";

const STAGES = ["", "chat", "facts", "trait", "summary", "dossier"];

export function TracesPanel() {
  const [stage, setStage] = useState("");
  const [rows, setRows] = useState<Trace[]>([]);
  const [open, setOpen] = useState<number | null>(null);

  async function load() {
    setRows(await getTraces(stage || undefined));
  }
  useEffect(() => { load().catch(() => void 0); }, [stage]);

  async function pin(t: Trace) {
    await patchTrace(t.id, { pinned: !t.pinned });
    load();
  }
  async function note(t: Trace, value: string) {
    await patchTrace(t.id, { note: value });
    load();
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-gray-200 p-2 text-sm">
        <select value={stage} onChange={(e) => setStage(e.target.value)} className="rounded border px-2 py-1">
          {STAGES.map((s) => <option key={s} value={s}>{s || "all stages"}</option>)}
        </select>
        <button onClick={() => load()} className="rounded border px-2 py-1">刷新</button>
        <span className="text-gray-400">{rows.length} 条</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {rows.map((t) => (
          <div key={t.id} className="border-b border-gray-100 px-3 py-2 text-sm">
            <div className="flex items-center gap-2">
              <button onClick={() => pin(t)} title="pin (protect from prune)">
                {t.pinned ? "★" : "☆"}
              </button>
              <span className="rounded bg-gray-100 px-1.5 text-xs">{t.stage}</span>
              <span className="text-gray-500">{t.model}</span>
              <span className="text-xs text-gray-400">
                {t.prompt_tokens ?? "?"}→{t.completion_tokens ?? "?"} tok · {t.duration_ms ?? "?"}ms
              </span>
              <span className="ml-auto text-xs text-gray-400">{t.created_at}</span>
              <button className="text-blue-600" onClick={() => setOpen(open === t.id ? null : t.id)}>
                {open === t.id ? "收起" : "展开"}
              </button>
            </div>
            {open === t.id && (
              <div className="mt-2 space-y-2">
                <input
                  defaultValue={t.note ?? ""}
                  placeholder="备注（好/塌了/抽错了…）"
                  className="w-full rounded border px-2 py-1 text-xs"
                  onBlur={(e) => note(t, e.target.value)}
                />
                <Field label="PROMPT" body={t.prompt} />
                <Field label="OUTPUT" body={t.output} />
              </div>
            )}
          </div>
        ))}
        {rows.length === 0 && <div className="p-4 text-gray-400">还没有 trace（聊几句、等后台建模触发）。</div>}
      </div>
    </div>
  );
}

function Field({ label, body }: { label: string; body: string | null }) {
  return (
    <div>
      <div className="text-xs font-semibold text-gray-500">{label}</div>
      <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-2 text-xs">
        {body ?? <span className="text-gray-400">（已滚动清除；pin 可保护未来的）</span>}
      </pre>
    </div>
  );
}
```

- [ ] **Step 2: Build + typecheck the frontend**

Run: `cd /Users/wangyuhao/Develop/personal/vellum/web && pnpm build`
Expected: `tsc && vite build` clean, `dist/` produced.

- [ ] **Step 3: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum add web && git -C /Users/wangyuhao/Develop/personal/vellum commit -m "feat(web): traces panel (filter by stage, expand full I/O, pin + note)"
```

---

## Done criteria

- Backend full suite green (`.venv/bin/python -m pytest -q`); fresh-checkout verified.
- `web` builds clean (`pnpm build`) and vitest still passes.
- Every modeling call (facts/trait/summary/dossier) + chat appears in `/inspect/traces` with full prompt/output; pin protects from prune; note persists.
- `你是谁` panel shows dossier + facts + per-dimension bars and history curves.
- Manual: chat a few turns → open `你是谁` (facts appear fast; traits after K turns) and `Traces` (rows accumulate, expandable).
- `messages` browse and trace-`replay` eval remain out of scope (later phases).

---

## Self-Review

- **Coverage:** trace-all-modeling-calls → Task 2 (capture+flush incl. failures). pin/protect → existing `traces.pin` + Task 3 endpoint + Task 6 UI. note → Task 1 (migration+DAO) + Task 3 + Task 6. 人格 viz (dossier/facts/multi-dim/curves) → Task 5. traces viz (filter/expand/full I/O) → Task 6. read-only + pin/note only → Tasks 3/6. messages-browse & replay-eval explicitly deferred.
- **Placeholders:** none; complete code per step. App.tsx→TracesPanel ordering called out (build after Task 6).
- **Type consistency:** `getModel/getTraces/patchTrace` + `ModelView/TraitDim/Fact/Trace` shapes match `/inspect/*` JSON (dossier str, traits[].history, traces[].pinned int/.note). `_flush_traces(calls, turn)` and `traces.record(...)` field names align with the client's captured-call record keys (`system_prompt`/`user_prompt`/`response`/`stage`/`status`).
