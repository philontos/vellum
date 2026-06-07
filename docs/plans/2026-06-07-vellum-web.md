# Vellum Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A minimal web client for Vellum — one **eternal scrolling conversation** (no "new chat") with a composer, streaming replies over SSE, and history loaded on mount. Plus the one backend endpoint it needs: `GET /history`.

**Architecture:** React + Vite + TypeScript + Tailwind in `web/`, sibling to `api/`. The SPA calls same-origin relative paths (`/health`, `/history`, `/chat`); in dev, Vite proxies them to FastAPI on `:18080`. `/chat` is POST-SSE, so streaming is consumed with `fetch` + `ReadableStream` (NOT `EventSource`, which is GET-only). The one logic-heavy frontend piece — the SSE frame parser — is a pure function with a vitest test; the rest is verified by build + a manual run.

**Tech Stack:** Backend: FastAPI (existing). Frontend: Vite 5, React 18, TypeScript, Tailwind 3, vitest (parser only).

**Depends on (merged):** `app.store.memory.recent_tail`, the existing `POST /chat` SSE route.

**Spec:** `docs/specs/2026-06-06-vellum-design.md` §2 (single eternal stream), §7 (consume loop), §10 (web).

---

## DESIGN DECISIONS BAKED IN (review these)

1. **Frontend tests = vitest on the pure SSE parser only.** The rest (components/hook) is verified by `pnpm build` + manual dev run. Full component testing (jsdom/RTL) is out of scope for a single-user local UI.
2. **Same-origin relative paths + Vite dev proxy.** No API base-URL config. Prod option (API serves `web/dist` static) is documented, not built.
3. **One eternal stream, no "new chat".** History loaded once on mount via `GET /history?limit=N` (default 200), newest at the bottom; composer pinned at the bottom.
4. **Environment caveat:** the implementer may lack node/pnpm/network in-sandbox. Backend `/history` is full pytest-TDD and MUST pass. Frontend files are authored; `pnpm install/test/build` is attempted and, if the toolchain/network is unavailable, reported as author-only (the user builds it). **Seeing it actually stream in a browser requires `pnpm dev` + a configured LLM/embedding key — that's the user's final verification, not the subagent's.**

---

## File Structure

```
api/app/routes/history.py        # GET /history
api/app/main.py                  # + include history router
api/tests/test_history_route.py

web/
  package.json · vite.config.ts · tsconfig.json · tsconfig.node.json
  index.html · postcss.config.js · tailwind.config.js
  src/
    main.tsx · App.tsx · index.css
    api/sse.ts            # pure: splitFrames(), parseData()
    api/sse.test.ts       # vitest
    api/client.ts         # getHistory(), streamChat()
    hooks/useChat.ts
    components/MessageList.tsx · MessageBubble.tsx · Composer.tsx
  README.md
```

Backend commands from `/Users/wangyuhao/Develop/personal/vellum/api` (python = `.venv/bin/python`); frontend from `/Users/wangyuhao/Develop/personal/vellum/web`.

---

## Task 1: Backend `GET /history`

**Files:** Create `api/app/routes/history.py`; Modify `api/app/main.py`; Test `api/tests/test_history_route.py`

- [ ] **Step 1: Write the failing test `api/tests/test_history_route.py`**

```python
from fastapi.testclient import TestClient


def test_history_returns_messages_oldest_first(migrated_db):
    from app.main import app
    from app.store import memory
    memory.append_message("user", "first")
    memory.append_message("assistant", "second")
    memory.append_message("user", "third")

    client = TestClient(app)
    r = client.get("/history?limit=2")
    assert r.status_code == 200
    data = r.json()["messages"]
    assert [m["content"] for m in data] == ["second", "third"]   # last 2, oldest-first
    assert data[0]["role"] == "assistant" and "turn" in data[0]


def test_history_empty(migrated_db):
    from app.main import app
    r = TestClient(app).get("/history")
    assert r.status_code == 200 and r.json()["messages"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_history_route.py -v`
Expected: FAIL — 404 (route not mounted)

- [ ] **Step 3: Create `api/app/routes/history.py`**

```python
"""GET /history — load the recent tail of the single eternal stream for the UI
on page load (oldest-first)."""
from fastapi import APIRouter

from app.store import memory

router = APIRouter()


@router.get("/history")
def history(limit: int = 200):
    return {"messages": memory.recent_tail(limit)}
```

- [ ] **Step 4: Mount it in `api/app/main.py`** — add the import and include:

```python
from app.routes import chat as chat_routes
from app.routes import history as history_routes

app = FastAPI(title="Vellum")
app.include_router(chat_routes.router)
app.include_router(history_routes.router)
```

(keep the existing `/health`.)

- [ ] **Step 5: Run tests, then full suite**

Run: `.venv/bin/python -m pytest tests/test_history_route.py -v`
Expected: 2 passed
Run: `.venv/bin/python -m pytest -q`
Expected: all prior (73) + 2 new pass.

- [ ] **Step 6: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum commit -am "feat: GET /history endpoint (load eternal stream tail)"
```

---

## Task 2: Frontend scaffold

**Files:** Create `web/package.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/index.html`, `web/postcss.config.js`, `web/tailwind.config.js`, `web/src/index.css`, `web/src/main.tsx`

- [ ] **Step 1: `web/package.json`**

```json
{
  "name": "vellum-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.2",
    "vite": "^5.4.11",
    "vitest": "^2.1.8"
  }
}
```

- [ ] **Step 2: `web/vite.config.ts`** (dev proxy to FastAPI; vitest config inline)

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/chat": "http://localhost:18080",
      "/history": "http://localhost:18080",
      "/health": "http://localhost:18080",
    },
  },
  test: { environment: "node" },
});
```

- [ ] **Step 3: `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: `web/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Vellum</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6: `web/postcss.config.js`**

```js
export default { plugins: { tailwindcss: {}, autoprefixer: {} } };
```

- [ ] **Step 7: `web/tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 8: `web/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root { height: 100%; margin: 0; }
```

- [ ] **Step 9: `web/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 10: Commit** (App.tsx comes in Task 6; this is just scaffold — don't run build yet)

```bash
git -C /Users/wangyuhao/Develop/personal/vellum add web && git -C /Users/wangyuhao/Develop/personal/vellum commit -m "feat(web): vite + react + tailwind scaffold"
```

---

## Task 3: Pure SSE parser + vitest

**Files:** Create `web/src/api/sse.ts`, `web/src/api/sse.test.ts`

- [ ] **Step 1: Write the failing test `web/src/api/sse.test.ts`**

```ts
import { describe, it, expect } from "vitest";
import { splitFrames, parseData } from "./sse";

describe("splitFrames", () => {
  it("splits complete \\n\\n frames and keeps the remainder", () => {
    const { frames, rest } = splitFrames('data: {"delta":"hi"}\n\ndata: {"delta":"the');
    expect(frames).toEqual(['data: {"delta":"hi"}']);
    expect(rest).toBe('data: {"delta":"the');
  });
  it("returns no frames when none complete", () => {
    const { frames, rest } = splitFrames("data: partial");
    expect(frames).toEqual([]);
    expect(rest).toBe("data: partial");
  });
});

describe("parseData", () => {
  it("parses a delta frame", () => {
    expect(parseData('data: {"delta":"hello"}')).toEqual({ type: "delta", text: "hello" });
  });
  it("recognizes [DONE]", () => {
    expect(parseData("data: [DONE]")).toEqual({ type: "done" });
  });
  it("ignores non-data / malformed lines", () => {
    expect(parseData(": comment")).toBeNull();
    expect(parseData("data: {not json}")).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails** (if pnpm available)

Run: `cd /Users/wangyuhao/Develop/personal/vellum/web && pnpm install && pnpm test`
Expected: FAIL — `./sse` has no `splitFrames`/`parseData`.
(If pnpm/node/network is unavailable in your sandbox, note it and proceed to write the code; the user will run vitest.)

- [ ] **Step 3: Create `web/src/api/sse.ts`**

```ts
export type SSEEvent = { type: "delta"; text: string } | { type: "done" };

/** Split a buffer into complete `\n\n`-terminated SSE frames + leftover. */
export function splitFrames(buffer: string): { frames: string[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  return { frames: parts, rest };
}

/** Parse one SSE frame's `data:` line. Returns null for comments / malformed. */
export function parseData(frame: string): SSEEvent | null {
  const line = frame.split("\n").find((l) => l.startsWith("data:"));
  if (!line) return null;
  const payload = line.slice(5).trim();
  if (payload === "[DONE]") return { type: "done" };
  try {
    const obj = JSON.parse(payload);
    if (typeof obj.delta === "string") return { type: "delta", text: obj.delta };
    return null;
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Run vitest to verify it passes** (if pnpm available)

Run: `cd /Users/wangyuhao/Develop/personal/vellum/web && pnpm test`
Expected: all sse tests pass. (If pnpm unavailable, note it.)

- [ ] **Step 5: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum add web && git -C /Users/wangyuhao/Develop/personal/vellum commit -m "feat(web): pure SSE frame parser + vitest"
```

---

## Task 4: API client

**Files:** Create `web/src/api/client.ts`

- [ ] **Step 1: Create `web/src/api/client.ts`**

```ts
import { splitFrames, parseData } from "./sse";

export type Message = { turn: number; role: "user" | "assistant"; content: string };

export async function getHistory(limit = 200): Promise<Message[]> {
  const r = await fetch(`/history?limit=${limit}`);
  if (!r.ok) throw new Error(`history failed: ${r.status}`);
  return (await r.json()).messages;
}

/**
 * POST /chat and stream the assistant reply. Calls onDelta for each text chunk.
 * Resolves when the stream completes ([DONE]).
 */
export async function streamChat(message: string, onDelta: (t: string) => void): Promise<void> {
  const r = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!r.ok || !r.body) throw new Error(`chat failed: ${r.status}`);

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { frames, rest } = splitFrames(buffer);
    buffer = rest;
    for (const frame of frames) {
      const ev = parseData(frame);
      if (ev?.type === "delta") onDelta(ev.text);
      else if (ev?.type === "done") return;
    }
  }
}
```

- [ ] **Step 2: Typecheck (if pnpm available)**

Run: `cd /Users/wangyuhao/Develop/personal/vellum/web && pnpm exec tsc --noEmit`
Expected: no errors. (If unavailable, note it.)

- [ ] **Step 3: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum add web && git -C /Users/wangyuhao/Develop/personal/vellum commit -m "feat(web): api client (getHistory + streamChat over fetch SSE)"
```

---

## Task 5: useChat hook

**Files:** Create `web/src/hooks/useChat.ts`

- [ ] **Step 1: Create `web/src/hooks/useChat.ts`**

```ts
import { useEffect, useRef, useState } from "react";
import { getHistory, streamChat, type Message } from "../api/client";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streaming, setStreaming] = useState(false);
  const nextTurn = useRef(0);

  useEffect(() => {
    getHistory()
      .then((m) => {
        setMessages(m);
        nextTurn.current = m.length ? m[m.length - 1].turn + 1 : 0;
      })
      .catch(() => void 0);
  }, []);

  async function send(text: string) {
    if (!text.trim() || streaming) return;
    const userTurn = nextTurn.current++;
    const asstTurn = nextTurn.current++;
    setMessages((m) => [
      ...m,
      { turn: userTurn, role: "user", content: text },
      { turn: asstTurn, role: "assistant", content: "" },
    ]);
    setStreaming(true);
    try {
      await streamChat(text, (delta) => {
        setMessages((m) =>
          m.map((msg) =>
            msg.turn === asstTurn ? { ...msg, content: msg.content + delta } : msg,
          ),
        );
      });
    } finally {
      setStreaming(false);
    }
  }

  return { messages, streaming, send };
}
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum add web && git -C /Users/wangyuhao/Develop/personal/vellum commit -m "feat(web): useChat hook (load history + optimistic streaming)"
```

---

## Task 6: Components + App + build

**Files:** Create `web/src/components/MessageBubble.tsx`, `web/src/components/MessageList.tsx`, `web/src/components/Composer.tsx`, `web/src/App.tsx`, `web/README.md`

- [ ] **Step 1: `web/src/components/MessageBubble.tsx`**

```tsx
import type { Message } from "../api/client";

export function MessageBubble({ m }: { m: Message }) {
  const mine = m.role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
          mine ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-900"
        }`}
      >
        {m.content || "…"}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: `web/src/components/MessageList.tsx`** (auto-scroll to bottom)

```tsx
import { useEffect, useRef } from "react";
import type { Message } from "../api/client";
import { MessageBubble } from "./MessageBubble";

export function MessageList({ messages }: { messages: Message[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  return (
    <div className="flex-1 space-y-3 overflow-y-auto px-4 py-6">
      {messages.map((m) => (
        <MessageBubble key={m.turn} m={m} />
      ))}
      <div ref={endRef} />
    </div>
  );
}
```

- [ ] **Step 3: `web/src/components/Composer.tsx`**

```tsx
import { useState } from "react";

export function Composer({ onSend, disabled }: { onSend: (t: string) => void; disabled: boolean }) {
  const [text, setText] = useState("");
  function submit() {
    const t = text.trim();
    if (!t) return;
    onSend(t);
    setText("");
  }
  return (
    <div className="flex gap-2 border-t border-gray-200 p-3">
      <textarea
        className="flex-1 resize-none rounded-xl border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring"
        rows={1}
        value={text}
        placeholder="跟它聊点什么…"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <button
        className="rounded-xl bg-blue-600 px-4 text-sm font-medium text-white disabled:opacity-40"
        onClick={submit}
        disabled={disabled}
      >
        发送
      </button>
    </div>
  );
}
```

- [ ] **Step 4: `web/src/App.tsx`**

```tsx
import { MessageList } from "./components/MessageList";
import { Composer } from "./components/Composer";
import { useChat } from "./hooks/useChat";

export default function App() {
  const { messages, streaming, send } = useChat();
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col">
      <header className="border-b border-gray-200 px-4 py-3 text-sm font-semibold text-gray-700">
        Vellum
      </header>
      <MessageList messages={messages} />
      <Composer onSend={send} disabled={streaming} />
    </div>
  );
}
```

- [ ] **Step 5: `web/README.md`**

```markdown
# Vellum web

Single eternal conversation UI for Vellum.

## Dev
1. Start the API (from `../api`, with `.env` configured — LLM + embedding key):
   `.venv/bin/python -m uvicorn app.main:app --port 18080`
2. Start the web dev server: `pnpm install && pnpm dev` → http://localhost:5173
   (Vite proxies `/chat`, `/history`, `/health` to the API.)

## Build
`pnpm build` → static assets in `dist/`. For a single-service deploy, have the API
serve `dist/` as static files (not wired by default).

## Test
`pnpm test` — vitest, covers the SSE parser.
```

- [ ] **Step 6: Build + test the frontend (if node/pnpm/network available)**

Run: `cd /Users/wangyuhao/Develop/personal/vellum/web && pnpm install && pnpm test && pnpm build`
Expected: vitest passes; `tsc && vite build` produces `dist/` with no type errors.
**If node/pnpm/network is unavailable in the sandbox:** do NOT fail the task — report "frontend authored, not built in-sandbox (no toolchain/network); user to run `pnpm install && pnpm build`." The backend pytest suite remaining green is the hard requirement.

- [ ] **Step 7: Add `web/dist` and `web/node_modules` to `.gitignore`** (verify they're covered — `node_modules/` and `dist/` already are from Plan 1's `.gitignore`; if `web/`-specific entries are needed, add them).

- [ ] **Step 8: Commit**

```bash
git -C /Users/wangyuhao/Develop/personal/vellum add web && git -C /Users/wangyuhao/Develop/personal/vellum commit -m "feat(web): chat UI (eternal stream, composer, streaming) + README"
```

---

## Done criteria

- `GET /history?limit=N` returns the recent tail oldest-first; pytest green (backend suite still fully green).
- The frontend is authored in full; the SSE parser has a passing vitest test; `pnpm build` succeeds where the toolchain is available.
- Manual end-to-end (user, needs a key): start API + `pnpm dev` → type in the browser → reply streams in, history persists across reload.

This is the last plan of the v1 sequence. After this, Vellum is end-to-end usable: chat in a browser, long-term memory, self-updating personal model, with an eval framework to measure it.

---

## Self-Review

- **Spec coverage:** §2/§10 single eternal stream UI → Tasks 2–6 (no "new chat"; one scroll + composer). §7 streaming consume → `client.streamChat` consuming the POST-SSE `/chat`. History load on mount → Task 1 (`/history`) + `useChat`. SSE-over-fetch (not EventSource, since POST) → `client.ts` + `sse.ts`. Dev proxy / build / deploy note → Task 2 vite config + Task 6 README.
- **Placeholder scan:** none. The "frontend not built in-sandbox" branch is an explicit, conditional fallback (toolchain availability), not a skipped requirement — backend tests remain the hard gate, and the parser is unit-tested.
- **Type consistency:** `Message {turn, role, content}` shared by `client.ts`, `useChat`, and components; `streamChat(message, onDelta)` / `getHistory(limit)` used consistently by the hook; `splitFrames`/`parseData` signatures match between `sse.ts`, its test, and `client.ts`. The `/history` response shape `{messages: [...]}` matches between `history.py`, its test, and `getHistory`.
