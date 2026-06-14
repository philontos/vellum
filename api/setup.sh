#!/usr/bin/env bash
#
# Vellum backend one-shot setup — encrypted by default.
#
#   cd api && ./setup.sh
#
# Idempotent: safe to re-run. It creates the venv, installs deps + the SQLCipher
# driver, generates a 256-bit key into api/.env (only if one isn't there yet),
# and creates the already-encrypted schema. An existing key is NEVER overwritten,
# so re-running on a synced device keeps the key that can open the pulled db.
#
# Prefer plaintext / no encryption? Skip this script and run the manual venv +
# `pip install -r requirements.txt` + uvicorn flow from the README instead.
set -euo pipefail

cd "$(dirname "$0")"   # always operate from api/

PYTHON=python3.12
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON not found. Install it:  brew install python@3.12" >&2
  exit 1
fi

# 1. venv — ONE venv holds everything, including the SQLCipher binding.
if [ ! -d .venv ]; then
  echo "==> creating .venv ($PYTHON)"
  "$PYTHON" -m venv .venv
fi
PIP=.venv/bin/pip
PY=.venv/bin/python

# 2. base Python deps
echo "==> installing requirements.txt"
"$PIP" install -q -r requirements.txt

# 3. native SQLCipher library + pkg-config (needed to build the binding)
OS="$(uname -s)"
if [ "$OS" = "Darwin" ]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "ERROR: Homebrew not found — install it from https://brew.sh, then re-run." >&2
    exit 1
  fi
  brew list sqlcipher  >/dev/null 2>&1 || { echo "==> brew install sqlcipher";  brew install sqlcipher; }
  brew list pkg-config >/dev/null 2>&1 || { echo "==> brew install pkg-config"; brew install pkg-config; }
  # Set defensively — harmless when sqlcipher is linked, required when it is keg-only.
  export PKG_CONFIG_PATH="$(brew --prefix sqlcipher)/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
elif [ "$OS" = "Linux" ]; then
  if ! command -v pkg-config >/dev/null 2>&1 || ! pkg-config --exists sqlcipher 2>/dev/null; then
    echo "ERROR: SQLCipher dev library / pkg-config not found. Install them, then re-run:" >&2
    echo "         sudo apt-get install libsqlcipher-dev pkg-config" >&2
    exit 1
  fi
else
  echo "ERROR: unsupported OS '$OS'. Install SQLCipher + pkg-config manually, then re-run." >&2
  exit 1
fi

# 4. the SQLCipher Python binding — into the SAME venv as everything else
echo "==> installing sqlcipher3 (SQLCipher Python binding)"
"$PIP" install -q sqlcipher3==0.6.2

# 5. .env — created from the template only if absent (never clobbers your edits)
if [ ! -f .env ]; then
  echo "==> creating .env from .env.example"
  cp .env.example .env
fi

# 6. key — generate only when .env has no active VELLUM_DB_KEY (idempotent).
#    The template ships it commented (`# VELLUM_DB_KEY=`), which does NOT match.
if grep -qE '^[[:space:]]*VELLUM_DB_KEY=.+' .env; then
  echo "==> VELLUM_DB_KEY already set in .env — keeping it (not regenerating)"
else
  KEY="$("$PY" -m app.keygen 2>/dev/null)"
  printf '\nVELLUM_DB_KEY=%s\n' "$KEY" >> .env
  echo ""
  echo "  ============================================================"
  echo "  VELLUM_DB_KEY (saved to api/.env):"
  echo "    $KEY"
  echo "  BACK THIS UP in a password manager. No backdoor — lose it and"
  echo "  the data is gone forever. Reuse THIS key on devices you sync to."
  echo "  ============================================================"
  echo ""
fi

# 7. create/upgrade the (encrypted) schema now, so the db is born as ciphertext.
#    sync.py reads the process env, not .env, so we load the two vars we need.
echo "==> creating/upgrading the encrypted database"
export VELLUM_DB_KEY="$(grep -E '^[[:space:]]*VELLUM_DB_KEY=' .env | tail -1 | cut -d= -f2- | tr -d '[:space:]')"
DATA_DIR="$(grep -E '^[[:space:]]*VELLUM_DATA_DIR=' .env | tail -1 | cut -d= -f2- | xargs || true)"
[ -n "${DATA_DIR:-}" ] && export VELLUM_DATA_DIR="$DATA_DIR"
"$PY" -c "from app.store import db; db.run_migrations()"

echo ""
echo "==> done. Fill in your LLM/embedding keys in api/.env, then start the backend:"
echo "      source .venv/bin/activate"
echo "      uvicorn app.main:app --port 18080 --env-file .env --reload"
