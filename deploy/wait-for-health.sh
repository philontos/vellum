#!/usr/bin/env bash
set -euo pipefail

URL="${1:?usage: wait-for-health.sh URL}"
ATTEMPTS="${VELLUM_HEALTH_ATTEMPTS:-30}"
INTERVAL="${VELLUM_HEALTH_INTERVAL:-1}"

if ! [[ "$ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: VELLUM_HEALTH_ATTEMPTS must be a positive integer" >&2
  exit 2
fi

attempt=1
while [ "$attempt" -le "$ATTEMPTS" ]; do
  if response="$(curl -fsS "$URL" 2>/dev/null)"; then
    printf '%s\n' "$response"
    exit 0
  fi

  if [ "$attempt" -lt "$ATTEMPTS" ]; then
    sleep "$INTERVAL"
  fi
  attempt="$((attempt + 1))"
done

echo "ERROR: health check did not succeed after $ATTEMPTS attempts: $URL" >&2
exit 1
