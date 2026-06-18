#!/usr/bin/env bash
# One command to (re)deploy Vellum on this machine: build the web, install/refresh
# the systemd service, and (re)start it. Re-runnable — run it again after a
# `git pull` to redeploy. Run from anywhere inside the repo.
#
#   ./deploy/start.sh                  # default port 18080
#   VELLUM_PORT=18090 ./deploy/start.sh   # if 18080 is taken (e.g. another app)
#
# Prereqs (once): api/.venv built via `cd api && ./setup.sh`, api/.env filled in,
# and Node + pnpm installed. See this directory's README.md.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${VELLUM_PORT:-18080}"
VENV="$REPO/api/.venv"
RUN_USER="$(id -un)"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO=sudo

echo "==> repo=$REPO  port=$PORT  user=$RUN_USER"

[ -x "$VENV/bin/uvicorn" ] || { echo "ERROR: no venv at $VENV — run: (cd api && ./setup.sh)" >&2; exit 1; }
[ -f "$REPO/api/.env" ]    || { echo "ERROR: missing $REPO/api/.env — copy .env.example and fill it in" >&2; exit 1; }
command -v pnpm >/dev/null || { echo "ERROR: pnpm not found — npm install -g pnpm" >&2; exit 1; }

# 1. build the web — the backend serves it same-origin (one process, one port)
( cd "$REPO/web" && pnpm install && pnpm build )

# 2. install/refresh the systemd unit (bound to 127.0.0.1, auto-restart, boot-start)
$SUDO tee /etc/systemd/system/vellum.service >/dev/null <<UNIT
[Unit]
Description=Vellum backend (FastAPI + web, localhost only)
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$REPO/api
Environment=VELLUM_WEB_DIST=$REPO/web/dist
Environment=VELLUM_PORT=$PORT
ExecStart=$VENV/bin/uvicorn app.main:app --host 127.0.0.1 --port \${VELLUM_PORT} --env-file .env
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

# 3. (re)start, picking up the fresh build + unit
$SUDO systemctl daemon-reload
$SUDO systemctl enable vellum >/dev/null 2>&1 || true
$SUDO systemctl restart vellum

# 4. health check
sleep 2
echo "==> health:"
curl -fsS "http://127.0.0.1:$PORT/health" && echo "  ✓ running on 127.0.0.1:$PORT"
echo
echo "Reach it from a laptop (VS Code: forward port $PORT — or on the laptop run):"
echo "  ssh -N -L 18888:127.0.0.1:$PORT $RUN_USER@<VPS_IP>   # then open http://localhost:18888"
