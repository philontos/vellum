# Vellum

A private, self-hosted **cognitive mirror** for one person or a small family. Each
account gets its own conversation, long-term memory, prose **dossier**, structured
**trait dimensions** (OCEAN / MBTI / Schwartz / regulatory focus), facts board,
vectors, and traces. There is no public signup or SaaS control plane.

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
  `python3.12` explicitly as shown below. macOS: `brew install python@3.12`.
  Debian/Ubuntu: `sudo apt-get install python3.12 python3.12-venv` (the `-venv`
  package is needed for `setup.sh` to build the virtualenv).
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

Family login is opt-in. To enable it for a new data directory, load `.env`, create
an owner at the password prompt, then set `VELLUM_AUTH_ENABLED=1` in `.env`:

```bash
set -a && source .env && set +a
.venv/bin/python -m app.auth.cli create \
  --username owner --display-name "Owner" --role owner
```

For an existing `data/vellum.db`, stop the running service and add
`--adopt-legacy`. The command copies the old main and observability databases into
the owner's private directory and keeps the originals in place for rollback.

### 2. Web UI (port 5173)

In a second terminal:

```bash
cd web
pnpm install
pnpm dev
```

### 3. Open it

Go to **http://localhost:5173** and start chatting. The dev server proxies `/auth`,
`/admin`, `/chat`, `/history`, `/inspect`, `/health` to the backend on `:18080`.

Backend-only sanity check: `curl http://localhost:18080/health` → `{"status":"ok"}`.

---

## Configuration (`.env`)

Copy `api/.env.example` to `api/.env` and fill it in.

| Variable | Required | What it is |
|---|---|---|
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | yes* | The primary chat model — any OpenAI-compatible `/chat/completions` endpoint. *Required when `LLM_CANDIDATE=primary`. |
| `LLM_CANDIDATE` | no | Legacy/default production selection: `primary` (default), `glm`, or `kimi`. Each Admin model route falls back to this value until that scenario is saved. |
| `EMBED_BASE_URL` / `EMBED_API_KEY` / `EMBED_MODEL` | yes* | The embedding model (`/embeddings`). *Falls back to `LLM_*` if unset — but set it explicitly when your chat provider has no embeddings. |
| `GLM_BASE_URL` / `GLM_API_KEY` / `GLM_MODEL` | no | Environment fallback for the named GLM candidate. URL and model default to the official endpoint and `glm-5.2`; setting the key enables it. |
| `KIMI_BASE_URL` / `KIMI_API_KEY` / `KIMI_MODEL` | no | Environment fallback for the named Kimi candidate. URL and model default to the official endpoint and `kimi-k3`; `MOONSHOT_API_KEY` is also accepted. |
| `VELLUM_DATA_DIR` | no | Data root. `prompts.db` is deployment-wide; family mode also stores `auth.db` plus `users/<id>/vellum.db`. Default `./data`. |
| `VELLUM_AUTH_ENABLED` | no | `1` enables private family login and per-account stores; default `0` keeps legacy mode. |
| `EVAL_GEN_BASE_URL` / `EVAL_GEN_API_KEY` / `EVAL_GEN_MODEL` | no | External evaluator model — only needed to *run* evals. |

Useful optional knobs (no `.env.example` entry, sane defaults):

| Variable | Default | What it does |
|---|---|---|
| `EMBED_API_STYLE` | `openai` | Set to `ark_multimodal` for Volcengine ARK's multimodal embeddings endpoint. |
| `LLM_SUPPORTS_TOOLS` | `1` | Set `0` for a chat model that can't tool-call (recall degrades to injected context). |
| `LLM_TIMEOUT_SECONDS` | `60` | Per-request timeout. |
| `VELLUM_PERSONA` | `neutral` | Persona file under `api/app/config/persona/`. |
| `VELLUM_DB_KEY` / `VELLUM_DB_KEY_FILE` | _(unset)_ | 256-bit hex key enabling SQLCipher at-rest encryption. Unset = plaintext. See *Encryption* below. |
| `VELLUM_AUTH_COOKIE_SECURE` | `0` | Keep `0` for HTTP over WireGuard/SSH; set `1` only when the site is served through HTTPS. |
| `VELLUM_AUTH_SESSION_DAYS` | `30` | Login session lifetime. Password changes and account disable revoke existing sessions. |
| `VELLUM_TIMEZONE` | `Asia/Shanghai` | Local timezone attached to model-facing user turns for relative-time and conversation-gap reasoning. Stored messages remain UTC and unchanged. |
| `VELLUM_SYNC_REMOTE` / `VELLUM_DEVICE_ID` | _(unset)_ | git remote + device label for `python -m app.sync`. |

To set the fallback production model, configure its credentials in Admin
(described below) or in the environment, set the selection, then restart the API
process. Embeddings remain on `EMBED_*`:

```bash
# GLM
LLM_CANDIDATE=glm
GLM_API_KEY=...

# or Kimi K3
LLM_CANDIDATE=kimi
KIMI_API_KEY=...       # MOONSHOT_API_KEY also works
```

Set `LLM_CANDIDATE=primary` to return to `LLM_BASE_URL` / `LLM_API_KEY` /
`LLM_MODEL`.

An owner can manage the primary integration (for example DeepSeek), GLM, and Kimi
without editing `.env`: open **Admin → Models**, enter the Base URL, model, and API
key, then choose **Validate**. **Save** remains disabled until that exact
configuration succeeds; changing any field invalidates the check. Keys are masked
by default and are returned only after an owner explicitly chooses **Show**. Saved
credentials live in the deployment-wide `prompts.db` and inherit its
SQLCipher-at-rest setting. A saved Admin configuration takes precedence over the
corresponding environment block.

The same page independently routes **Chat replies**, **Background modeling**, and
the **Evaluation default** to any configured integration. Route changes take
effect without a process restart; a scenario without a saved route follows
`LLM_CANDIDATE`. In family mode the page and every credential/route endpoint are
owner-only; legacy single-user mode retains its existing owner-equivalent Admin
behavior.

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

Your data root (`api/data/`) is itself a tiny git repo. Both modes track the shared
encrypted `prompts.db`; legacy mode also tracks `vellum.db`, while family mode
tracks encrypted `auth.db` and every `users/<id>/vellum.db`. The sync commands
push only ciphertext. Treat it as a baton: one active device at a time.

**One-time setup:** create an empty **private** repo (e.g. on GitHub, named
`vellum-data` — do *not* add a README/.gitignore, leave it empty). Then on your
first device:

```bash
cd api && source .venv/bin/activate
echo 'VELLUM_SYNC_REMOTE=git@github.com:you/vellum-data.git' >> .env

set -a && source .env && set +a          # sync reads the process env, not .env
python -m app.sync push                  # checkpoint -> commit canonical DBs -> push
python -m app.sync status                # ahead / behind the remote
```

**Adding a second device:** install the same way, but **before** running
`./setup.sh` put your *existing* key into `api/.env` — the encrypted db only opens
with the key that created it, and setup keeps an existing key instead of making a
new one. Then point it at the same remote and pull:

```bash
set -a && source .env && set +a
python -m app.sync pull                  # hard-resets canonical DBs to the remote;
                                         # refuses if you have un-pushed local changes
```

Per-user `observability.db` files (traces/evals) stay per-device. The key never
goes in the repo — carry it out-of-band.

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
  `python -m app.bootstrap` (from `api/`, after exporting `.env`). Never edit a
  committed migration — add a new one.
- **`.env` is not auto-loaded by the app.** Pass it via `uvicorn --env-file .env`
  (shown above) or export it into your shell. Tests and evals read the process
  environment directly.
- **Embeddings need a real `/embeddings` provider.** DeepSeek, Claude, and
  Moonshot don't offer one — point `EMBED_*` at OpenAI, a local Ollama (`bge-m3`),
  Volcengine ARK, etc. **Changing the embedding model invalidates stored
  embeddings** (different dimension) — clear the `embeddings` table (or delete
  `api/data/` to reset) so they rebuild as you chat.
- **Private family accounts.** There is no web signup: the machine owner provisions,
  lists, disables, and resets accounts with `python -m app.auth.cli`. Passwords use
  Argon2id; opaque session tokens are stored only as SHA-256 digests. Each account's
  text, embeddings, model, and traces live in its own SQLite files. HNSW graphs are
  rebuilt into separate per-user memory caches.
- **Prompt releases.** The owner-only **Prompts** tab edits a deployment-wide draft
  workspace shared by every account. Saving does not affect live calls; publishing
  validates every template and atomically activates one immutable release. Loading
  an older release creates a draft for review before it is republished. Every
  catalog entry also has a bilingual usage guide covering its runtime path and
  editing constraints; guide text is code-owned metadata and is never sent to the
  model or included in a release.
- **Reasoning models:** chain-of-thought (`reasoning_content` / `reasoning`) is
  captured into traces for inspection, but never streamed into the chat answer.
- **Feishu/Lark adapter (deprecated):** existing deployments remain compatible,
  but this entry point is maintenance-only. New chat integration work targets the
  web path; the adapter still inherits the selected production model while enabled.
- **Tests:** backend `pytest` (from `api/`); web `pnpm test` (from `web/`).
- **Evals:** `python -m evals.run all` from `api/` (requires `EVAL_GEN_*`). The
  keyless harness tests run as part of `pytest`.

---

## Inspecting your model

- **You** — live dossier, its grounded portrait claims and user citations, facts,
  and trait dimensions, with per-dimension history curves as they shift over the
  conversation.
- **Traces** — every LLM call (chat + facts/trait/summary/dossier evidence/render),
  with the full prompt, output, reasoning, token counts, and latency. Pin a trace (★) to protect
  it from rolling pruning; add a note to mark good/bad results while you tune.
- **Prompts** (owner only) — production chat, memory-modeling, trait, and tool
  prompts; per-Prompt usage guides plus an explicit draft/save/publish workflow
  with immutable release history. Dossier evidence extraction and final portrait
  rendering are independently editable prompts.
- **Evals** (owner only) — fork any completed conversation turn into an independent
  evaluation archive using its original Prompt, an immutable release, or a named
  on-the-spot system Prompt. Each run can use the primary model, GLM, or Kimi K3;
  its initial selection follows the Admin evaluation route, while an explicit
  per-run choice does not change the live-chat route. Each archive freezes the
  source, baseline Prompt, evaluated Prompt, and complete model inputs; its detail
  view shows a line diff plus every repeated result side by side. Archives live in
  the per-account observability database, remain available independently of
  conversation history, and never append chat messages or trigger background
  modeling.

### Rebuilding Schwartz from message history

Schwartz V2 is rebuildable from the canonical live user messages in SQLite; it
does not depend on retained traces or the previous aggregate score. From `api/`,
load the same environment (especially the database key) used by the service and
preview the source range first:

```bash
set -a
source .env
set +a
.venv/bin/python -m app.model_loop.rebuild schwartz --username owner
```

The command is read-only unless `--apply` is present. In family-auth mode,
`--username` is required so one account is selected explicitly; omit it for the
legacy single-user store. Before rebuilding a deployment with immutable Prompt
releases, inspect and publish the guarded V2 Prompt upgrade. It refuses to publish
when unrelated Prompt drafts are pending:

```bash
.venv/bin/python -m app.prompts.maintenance schwartz-v2 --username owner
.venv/bin/python -m app.prompts.maintenance schwartz-v2 --username owner --apply
```

Then apply the rebuild with that same active Prompt snapshot:

```bash
.venv/bin/python -m app.model_loop.rebuild schwartz \
  --username owner --batch-turns 6 --prompt-source active --apply
```

Use `--batch-turns 1` to extract each user turn independently, or a larger span to
give the assessor more local context. Assistant messages and soft-deleted turns
are never treated as trait evidence. All LLM results are staged in memory; only
after every batch succeeds are Schwartz current/history/evidence rows replaced in
one transaction. Other dimensions and the normal modeling cursor are untouched.
If messages or the live Schwartz projection change during the run, the swap aborts
and keeps the old model. Stop the chat service for the duration of `--apply`; this
also excludes a background trait job that started before the maintenance command
and could otherwise finish just after it. `--prompt-release ID` is available for
controlled comparisons; the code-owned prompt remains the rebuild default, while
the guarded workflow above deliberately pins rebuild and future online turns to
the same active V2 release.
