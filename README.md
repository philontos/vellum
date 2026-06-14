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
web/   React + Vite + Tailwind   — Chat / You (your model) / Traces panels
```

The web UI ships in English (default) and 中文 — toggle with the **中 / EN**
switch in the header; the choice is remembered in `localStorage`.

---

## Requirements

- **Python 3.12** — your system `python3` may be older (macOS ships 3.9), so use
  `python3.12` explicitly as shown below. Install with `brew install python@3.12`.
- **Node 18+** with **pnpm**
- **SQLCipher** native library + `pkg-config` — for the default encrypted setup.
  macOS: `brew install sqlcipher pkg-config`; Linux: `apt-get install libsqlcipher-dev pkg-config`.
  On macOS `api/setup.sh` installs these for you.
- An OpenAI-compatible **chat** endpoint, and an OpenAI-compatible **embeddings**
  endpoint (same provider or different — see notes; DeepSeek/Claude/Moonshot have
  no embeddings, so you'll point `EMBED_*` elsewhere).

---

## Quick start

Two services: the **backend** (FastAPI, port 18080) and the **web UI** (Vite,
port 5173). Start the backend first — the UI proxies to it.

### 1. Backend (port 18080)

```bash
cd api
./setup.sh                    # venv + deps + SQLCipher + a generated key in api/.env
                              # (back up the key it prints!) — see Encryption below

# fill in your LLM/embedding keys in the api/.env it created — see Configuration

source .venv/bin/activate
uvicorn app.main:app --port 18080 --env-file .env --reload
```

`setup.sh` is idempotent and leaves you **encrypted by default**: it creates the
venv, installs deps + the SQLCipher driver, writes a 256-bit `VELLUM_DB_KEY` into
`api/.env`, and creates the already-encrypted schema. Re-run it any time; it never
regenerates an existing key. The schema is also created/upgraded automatically on
every startup, so there's no separate migration step. Prefer plaintext / no
encryption? See the end of *Encryption*. Leave this terminal running.

### 2. Web UI (port 5173)

In a second terminal:

```bash
cd web
pnpm install
pnpm dev
```

### 3. Open it

Go to **http://localhost:5173** and start chatting. The dev server proxies `/chat`,
`/history`, `/inspect`, `/health` to the backend on `:18080`.

Backend-only sanity check: `curl http://localhost:18080/health` → `{"status":"ok"}`.

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
| `VELLUM_DB_KEY` / `VELLUM_DB_KEY_FILE` | _(unset)_ | 256-bit hex key enabling SQLCipher at-rest encryption. Unset = plaintext. See *Encryption* below. |
| `VELLUM_SYNC_REMOTE` / `VELLUM_DEVICE_ID` | _(unset)_ | git remote + device label for `python -m app.sync`. |

---

## Encryption

`api/setup.sh` makes the backend **encrypted by default**: the **whole database**
is transparently AES-256 encrypted via SQLCipher — every query, migration, and the
vector index keep working unchanged. Running it once gets you there:

```bash
cd api
./setup.sh
```

What it does (all idempotent — safe to re-run):

1. creates `.venv` (Python 3.12) and installs `requirements.txt`;
2. installs the SQLCipher native library + `pkg-config` (macOS, via Homebrew) and
   the `sqlcipher3` driver into the **same** venv;
3. generates a 256-bit key into `api/.env` as `VELLUM_DB_KEY` — **printed once;
   back it up;**
4. creates the already-encrypted schema, so the db is born as ciphertext.

- **The key is yours alone.** `api/.env` is git-ignored and never leaves the
  machine; a stolen synced repo or `data/` dir is just ciphertext. There is **no
  backdoor — lose the key and the data is gone forever.** Reuse the *same* key on
  any device you sync to (below).
- **Vectors are covered too:** embeddings live inside `vellum.db` (no separate
  plaintext `index.bin`); the HNSW index is rebuilt in memory on first use.
- The app **refuses to start** with a clear message if the db is encrypted but
  `VELLUM_DB_KEY` is missing or wrong.

> **Already have a plaintext `data/`?** Encrypt it in place once (idempotent):
> ```bash
> VELLUM_DB_KEY=<64-hex> python -m app.encrypt_db
> ```

### Multi-device sync (optional)

Your data dir (`api/data/`) is itself a tiny git repo whose only tracked file is the
encrypted `vellum.db`; the sync commands manage it for you and push it to a remote
that only ever sees ciphertext. Treat it as a baton: one active device at a time.

**One-time setup:** create an empty **private** repo (e.g. on GitHub, named
`vellum-data` — do *not* add a README/.gitignore, leave it empty). Then on your
first device:

```bash
cd api && source .venv/bin/activate
echo 'VELLUM_SYNC_REMOTE=git@github.com:you/vellum-data.git' >> .env

set -a && source .env && set +a          # sync reads the process env, not .env
python -m app.sync push                  # checkpoint -> commit vellum.db -> push
python -m app.sync status                # ahead / behind the remote
```

**Adding a second device:** install the same way, but **before** running
`./setup.sh` put your *existing* key into `api/.env` — the encrypted db only opens
with the key that created it, and setup keeps an existing key instead of making a
new one. Then point it at the same remote and pull:

```bash
set -a && source .env && set +a
python -m app.sync pull                  # hard-resets local vellum.db to the remote;
                                         # refuses if you have un-pushed local changes
```

Only `vellum.db` is synced (the canonical state); `observability.db` (traces/evals)
stays per-device. The key never goes in the repo — carry it out-of-band.

### Prefer plaintext (no encryption)?

Skip `setup.sh` and do the manual flow — no key, no SQLCipher needed:

```bash
cd api
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                     # leave VELLUM_DB_KEY unset
uvicorn app.main:app --port 18080 --env-file .env --reload
```

## Notes

- **Migrations run automatically on app startup** (FastAPI lifespan) and are
  forward-only and idempotent. For CLI-only flows you can still run them by hand:
  `python -c "from app.store import db; db.run_migrations()"` (from `api/`, with
  `VELLUM_DATA_DIR` matching your `.env`). Never edit a committed migration — add a new one.
- **`.env` is not auto-loaded by the app.** Pass it via `uvicorn --env-file .env`
  (shown above) or export it into your shell. Tests and evals read the process
  environment directly.
- **Embeddings need a real `/embeddings` provider.** DeepSeek, Claude, and
  Moonshot don't offer one — point `EMBED_*` at OpenAI, a local Ollama (`bge-m3`),
  Volcengine ARK, etc. **Changing the embedding model invalidates stored
  embeddings** (different dimension) — clear the `embeddings` table (or delete
  `api/data/` to reset) so they rebuild as you chat.
- **Single-user, local only.** No auth, no accounts. All text and embeddings live
  in SQLite (`api/data/vellum.db`); the HNSW vector graph is rebuilt in memory from
  it on demand. To reset everything, delete `api/data/`.
- **Reasoning models:** chain-of-thought (`reasoning_content` / `reasoning`) is
  captured into traces for inspection, but never streamed into the chat answer.
- **Tests:** backend `pytest` (from `api/`); web `pnpm test` (from `web/`).
- **Evals:** `python -m evals.run all` from `api/` (requires `EVAL_GEN_*`). The
  keyless harness tests run as part of `pytest`.

---

## Inspecting your model

- **You** — live dossier, facts, and trait dimensions, with per-dimension
  history curves as they shift over the conversation.
- **Traces** — every LLM call (chat + facts/trait/summary/dossier), with the full
  prompt, output, reasoning, token counts, and latency. Pin a trace (★) to protect
  it from rolling pruning; add a note to mark good/bad results while you tune.
