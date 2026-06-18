#!/usr/bin/env bash
# Update Vellum to the latest code and redeploy in one shot: git pull + start.sh
# (which rebuilds the web, refreshes the systemd unit, and restarts the service).
# Run from anywhere inside the repo. VELLUM_PORT passes through to start.sh.
#
#   ./deploy/update.sh                  # default port 18080
#   VELLUM_PORT=18090 ./deploy/update.sh   # the port you deployed with
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
echo "==> pulling latest into $REPO"
git -C "$REPO" pull --ff-only
exec "$REPO/deploy/start.sh"
