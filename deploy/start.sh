#!/usr/bin/env bash
# The ONE command to (re)deploy Vellum on this box. Run it after every code change
# — you pull the code yourself, this script does the rest:
#
#   ./deploy/start.sh                     # default port 18080
#   VELLUM_PORT=18090 ./deploy/start.sh   # if 18080 is taken (e.g. another app)
#
# It refreshes the backend (venv + Python deps + sqlcipher driver + schema, via
# api/setup.sh — so a pull that adds requirements is picked up automatically),
# rebuilds the web, refreshes the systemd unit, and restarts the service — whose
# startup also applies any new DB migrations. Idempotent; safe to re-run.
#
# First time only: `cd api && ./setup.sh`, then fill api/.env (LLM_*, EMBED_*,
# VELLUM_DB_KEY). After that, this one script is all you need. Node + pnpm required.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${VELLUM_PORT:-18080}"
VENV="$REPO/api/.venv"
RUN_USER="$(id -un)"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO=sudo

echo "==> repo=$REPO  port=$PORT  user=$RUN_USER"

# You configure api/.env yourself; this script won't create or edit it — it just
# refuses to deploy without it (an unconfigured service is worse than a clear stop).
[ -f "$REPO/api/.env" ] || { echo "ERROR: missing $REPO/api/.env — first time: (cd api && ./setup.sh) then fill it in" >&2; exit 1; }
command -v pnpm >/dev/null || { echo "ERROR: pnpm not found — npm install -g pnpm" >&2; exit 1; }

# 1. backend bootstrap — venv, Python deps, sqlcipher driver, schema. Idempotent;
#    this is what picks up new requirements.txt deps after a pull. Migrations also
#    re-run here, and again on service startup (app lifespan), so the db is current.
"$REPO/api/setup.sh"

# 2. web — the backend serves it same-origin (one process, one port)
( cd "$REPO/web" && pnpm install && pnpm build )

# 3. install/refresh the systemd unit (127.0.0.1 only, auto-restart, boot-start, hardened)
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
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT

# 4. (re)start, picking up the fresh build + unit; startup applies new migrations
$SUDO systemctl daemon-reload
$SUDO systemctl enable vellum >/dev/null 2>&1 || true
$SUDO systemctl restart vellum

# 5. health check
sleep 2
echo "==> health:"
curl -fsS "http://127.0.0.1:$PORT/health" && echo "  ✓ running on 127.0.0.1:$PORT"
echo
echo "Reach it from a laptop (VS Code: forward port $PORT — or on the laptop run):"
echo "  ssh -N -L 18888:127.0.0.1:$PORT $RUN_USER@<VPS_IP>   # then open http://localhost:18888"
