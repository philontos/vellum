#!/usr/bin/env bash
# Vellum encrypted backup: checkpoint + push the ciphertext db to the private
# remote. Designed for cron. Reads api/.env for VELLUM_DB_KEY / VELLUM_SYNC_REMOTE
# / VELLUM_DATA_DIR (app.sync reads the process env, not .env, so we source it).
set -euo pipefail

API_DIR="${VELLUM_API_DIR:-/opt/vellum/api}"
cd "$API_DIR"
set -a
source .env
set +a
exec .venv/bin/python -m app.sync push
