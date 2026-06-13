# Vellum

A single-user, local **cognitive mirror**: one eternal chat stream with long-term
memory, plus a background loop that silently models *you* — a prose **dossier**,
structured **trait dimensions** (OCEAN / MBTI / Schwartz / regulatory focus,
Bayesian-smoothed), and a **facts** pin-board. The model is fed back as quiet
background reference, never a lens — the current question stays the figure. Any
OpenAI-compatible chat model plugs in; every LLM call is captured as an
inspectable trace.

```
api/   FastAPI + SQLite + hnswlib — chat loop (sync) + background modeling (async)
web/   React + Vite + Tailwind   — Chat / You (your model) / Traces panels
```

---

## Quick start

**Prerequisites:** Python 3.12 · Node 18+ with pnpm · an OpenAI-compatible **chat**
endpoint and an **embeddings** endpoint (same provider or different — DeepSeek /
Claude / Moonshot have no embeddings, so point `EMBED_*` elsewhere; see
[Configuration](#configuration-env)).

### 1. Backend (port 18080)

```bash
cd api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # fill in your keys — see Configuration

uvicorn app.main:app --port 18080 --env-file .env --reload
```

The SQLite schema is created/upgraded automatically on startup.

### 2. Frontend (port 5173)

```bash
cd web
pnpm install
pnpm dev
```

Open **http://localhost:5173** — start the backend first; the dev server proxies
`/chat`, `/history`, `/inspect`, `/health` to `:18080`. The UI ships in English
(default) and 中文 — toggle with **中 / EN** in the header (remembered in
`localStorage`).

---

## Your database

Everything you type and everything Vellum infers about you lives in **one SQLite
file** — `api/data/vellum.db` (messages, facts, traits, dossier, **and** the
embeddings). `api/data/observability.db` holds diagnostic traces + eval runs. To
wipe everything, delete `api/data/`.

### Encrypt it at rest (optional)

By default the db is plaintext. Set a key and the **whole database is transparently
AES-256 encrypted** via SQLCipher — every query, migration, and the vector index
keep working unchanged. Opt-in: no key = plaintext, exactly as before.

```bash
# 0. one-time: install the SQLCipher driver (not auto-installed)
brew install sqlcipher                                              # macOS
PKG_CONFIG_PATH=/opt/homebrew/opt/sqlcipher/lib/pkgconfig pip install sqlcipher3==0.6.2

# 1. generate a 256-bit key — printed ONCE, never saved
python -m app.keygen          # store it in a password manager / key file

# 2. encrypt your existing db in place (idempotent)
VELLUM_DB_KEY=<64-hex> python -m app.encrypt_db

# 3. run with the key supplied at runtime (kept OUTSIDE the data dir)
export VELLUM_DB_KEY=<64-hex>   # or: VELLUM_DB_KEY_FILE=/path/to/key.hex
uvicorn app.main:app --port 18080 --env-file .env
```

- **The key is yours alone** — never written into the data dir, so a stolen `data/`
  is just ciphertext. A raw 256-bit key has no passphrase to brute-force and
  **no backdoor: lose it and the data is gone forever.**
- **Vectors are covered too** — embeddings live inside `vellum.db` (no plaintext
  `index.bin`); the HNSW index is rebuilt in memory on first use.
- If the db is encrypted but `VELLUM_DB_KEY` is unset, the app **refuses to start**
  with a clear message instead of failing cryptically.

### Sync across devices (optional)

Because the encrypted file is opaque, you can push it to a git remote (a **private**
repo is recommended) and pull it on another machine. Treat it as a baton — one
active device at a time; the key travels out-of-band, never in the repo.

```bash
export VELLUM_SYNC_REMOTE=git@github.com:you/vellum-data.git
python -m app.sync push      # checkpoint → commit vellum.db → push
python -m app.sync pull      # fetch → refuses if you have un-pushed local changes
python -m app.sync status    # ahead / behind the remote
```

Only `vellum.db` (the canonical state) is synced; `observability.db` stays
per-device.

---

## Configuration (`.env`)

Copy `api/.env.example` to `api/.env` and fill it in. `.env` is **not** auto-loaded
— pass it via `uvicorn --env-file .env` or export it into your shell (tests and
evals read the process environment directly).

| Variable | Required | What it is |
|---|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | yes | The chat model — any OpenAI-compatible `/chat/completions` endpoint. |
| `EMBED_BASE_URL` / `EMBED_API_KEY` / `EMBED_MODEL` | yes* | The embedding model (`/embeddings`). *Falls back to `LLM_*` if unset — but set it explicitly when your chat provider has no embeddings. |
| `VELLUM_DATA_DIR` | no | Where the SQLite dbs live. Default `./data`. |
| `VELLUM_DB_KEY` / `VELLUM_DB_KEY_FILE` | no | 256-bit hex key enabling at-rest encryption (see [Your database](#your-database)). Unset = plaintext. |
| `VELLUM_SYNC_REMOTE` / `VELLUM_DEVICE_ID` | no | git remote + device label for `python -m app.sync`. |
| `EVAL_GEN_BASE_URL` / `EVAL_GEN_API_KEY` / `EVAL_GEN_MODEL` | no | External evaluator model — only needed to *run* evals. |

Useful optional knobs (sane defaults, no `.env.example` entry):

| Variable | Default | What it does |
|---|---|---|
| `EMBED_API_STYLE` | `openai` | Set to `ark_multimodal` for Volcengine ARK's multimodal embeddings endpoint. |
| `LLM_SUPPORTS_TOOLS` | `1` | Set `0` for a chat model that can't tool-call (recall degrades to injected context). |
| `LLM_TIMEOUT_SECONDS` | `60` | Per-request timeout. |
| `VELLUM_PERSONA` | `neutral` | Persona file under `api/app/config/persona/`. |

---

## Notes

- **Migrations run automatically on startup** (FastAPI lifespan), forward-only and
  idempotent. For CLI-only flows run them by hand:
  `python -c "from app.store import db; db.run_migrations()"` (from `api/`, with
  `VELLUM_DATA_DIR` matching your `.env`). Never edit a committed migration — add a new one.
- **Embeddings need a real `/embeddings` provider.** DeepSeek, Claude, and Moonshot
  don't offer one — point `EMBED_*` at OpenAI, a local Ollama (`bge-m3`), Volcengine
  ARK, etc. **Changing the embedding model invalidates stored embeddings** (different
  dimension) — clear the `embeddings` table (or delete `api/data/`) so they rebuild as you chat.
- **Single-user, local only.** No auth, no accounts.
- **Reasoning models:** chain-of-thought (`reasoning_content` / `reasoning`) is
  captured into traces for inspection, but never streamed into the chat answer.
- **Tests:** backend `pytest` (from `api/`); web `pnpm test` (from `web/`).
- **Evals:** `python -m evals.run all` from `api/` (requires `EVAL_GEN_*`). The
  keyless harness tests run as part of `pytest`.

---

## Inspecting your model

- **You** — live dossier, facts, and trait dimensions, with per-dimension history
  curves as they shift over the conversation.
- **Traces** — every LLM call (chat + facts/trait/summary/dossier), with the full
  prompt, output, reasoning, token counts, and latency. Pin a trace (★) to protect
  it from rolling pruning; add a note to mark good/bad results while you tune.
