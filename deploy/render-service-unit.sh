#!/usr/bin/env bash
set -euo pipefail

: "${VELLUM_REPO:?VELLUM_REPO is required}"
: "${VELLUM_RUN_USER:?VELLUM_RUN_USER is required}"

HOST="${VELLUM_HOST:-127.0.0.1}"
PORT="${VELLUM_PORT:-18080}"
VENV="$VELLUM_REPO/api/.venv"

case "$HOST" in
  0.0.0.0 | :: | '[::]')
    echo "ERROR: refusing wildcard VELLUM_HOST=$HOST; bind an exact interface address" >&2
    exit 2
    ;;
esac

cat <<UNIT
[Unit]
Description=Vellum backend (FastAPI + web)
After=network-online.target
Wants=network-online.target

[Service]
User=$VELLUM_RUN_USER
WorkingDirectory=$VELLUM_REPO/api
Environment=VELLUM_WEB_DIST=$VELLUM_REPO/web/dist
Environment=VELLUM_HOST=$HOST
Environment=VELLUM_PORT=$PORT
ExecStart=$VENV/bin/uvicorn app.main:app --host \${VELLUM_HOST} --port \${VELLUM_PORT} --env-file .env
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
