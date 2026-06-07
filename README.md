# Vellum

A single-user, local **cognitive mirror**: one eternal chat stream with long-term
memory, plus a background loop that silently models *you* — a prose **dossier**,
structured **trait dimensions** (OCEAN / MBTI / Schwartz / regulatory focus,
Bayesian-smoothed), and a **facts** pin-board. The model is fed back as quiet
background reference, never a lens — the current question stays the figure.

Any OpenAI-compatible chat model plugs in. Every LLM call (chat *and* background
modeling) is captured as an inspectable trace.

```
api/   FastAPI + SQLite + hnswlib — chat loop (sync) + background modeling (async)
web/   React + Vite + Tailwind   — Chat / 你是谁 (your model) / Traces panels
```

---

## Requirements

- **Python 3.12**
- **Node 18+** with **pnpm**
- An OpenAI-compatible **chat** endpoint, and an OpenAI-compatible **embeddings**
  endpoint (same provider or different — see notes; DeepSeek/Claude/Moonshot have
  no embeddings, so you'll point `EMBED_*` elsewhere).

---

## Run it

### 1. Backend (port 18080)

```bash
cd api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then fill in your keys (see Configuration below)

# Create / upgrade the SQLite schema. Migrations are NOT auto-run — see Notes.
python -c "from app.store import db; db.run_migrations()"

uvicorn app.main:app --port 18080 --env-file .env --reload
```

### 2. Frontend (port 5173)

```bash
cd web
pnpm install
pnpm dev
```

Open **http://localhost:5173**. The dev server proxies `/chat`, `/history`,
`/inspect`, `/health` to the backend on `:18080`, so start the backend first.

---

## Configuration (`.env`)

Copy `api/.env.example` to `api/.env` and fill it in.

| Variable | Required | What it is |
|---|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | yes | The chat model — any OpenAI-compatible `/chat/completions` endpoint. |
| `EMBED_BASE_URL` / `EMBED_API_KEY` / `EMBED_MODEL` | yes* | The embedding model (`/embeddings`). *Falls back to `LLM_*` if unset — but set it explicitly when your chat provider has no embeddings. |
| `VELLUM_DATA_DIR` | no | Where the SQLite db + vector index live. Default `./data`. |
| `EVAL_GEN_BASE_URL` / `EVAL_GEN_API_KEY` / `EVAL_GEN_MODEL` | no | External evaluator model — only needed to *run* evals. |

Useful optional knobs (no `.env.example` entry, sane defaults):

| Variable | Default | What it does |
|---|---|---|
| `EMBED_API_STYLE` | `openai` | Set to `ark_multimodal` for Volcengine ARK's multimodal embeddings endpoint. |
| `LLM_SUPPORTS_TOOLS` | `1` | Set `0` for a chat model that can't tool-call (recall degrades to injected context). |
| `LLM_TIMEOUT_SECONDS` | `60` | Per-request timeout. |
| `VELLUM_PERSONA` | `neutral` | Persona file under `api/app/config/persona/`. |

---

## Notes / 注意事项

- **Migrations are not auto-run on startup.** After the first setup, and after any
  pull that adds a file under `api/migrations/`, re-run:
  `python -c "from app.store import db; db.run_migrations()"` (from `api/`, with
  `VELLUM_DATA_DIR` matching your `.env` if you customized it). They are
  forward-only and idempotent — never edit a committed migration, add a new one.
- **`.env` is not auto-loaded by the app.** Pass it via `uvicorn --env-file .env`
  (shown above) or export it into your shell. Tests and evals read the process
  environment directly.
- **Embeddings need a real `/embeddings` provider.** DeepSeek, Claude, and
  Moonshot don't offer one — point `EMBED_*` at OpenAI, a local Ollama (`bge-m3`),
  Volcengine ARK, etc. **Changing the embedding model invalidates the index** —
  delete `api/data/vectors` and let it rebuild.
- **Single-user, local only.** No auth, no accounts. All text lives in SQLite
  (`api/data/vellum.db`); embeddings + integer labels live in `api/data/vectors`.
  To reset everything, delete `api/data/`.
- **Reasoning models:** chain-of-thought (`reasoning_content` / `reasoning`) is
  captured into traces for inspection, but never streamed into the chat answer.
- **Tests:** backend `pytest` (from `api/`); web `pnpm test` (from `web/`).
- **Evals:** `python -m evals.run all` from `api/` (requires `EVAL_GEN_*`). The
  keyless harness tests run as part of `pytest`.

---

## Inspecting your model

- **你是谁** — live dossier, facts, and trait dimensions, with per-dimension
  history curves as they shift over the conversation.
- **Traces** — every LLM call (chat + facts/trait/summary/dossier), with the full
  prompt, output, reasoning, token counts, and latency. Pin a trace (★) to protect
  it from rolling pruning; add a note to mark good/bad results while you tune.
