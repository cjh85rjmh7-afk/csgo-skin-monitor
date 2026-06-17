#!/usr/bin/env bash
# Wrapper to run the monitor locally (e.g. via cron on Kali Linux).
# Reads the Discord webhook from a local, untracked secret file.
set -euo pipefail

# Directory this script lives in (so cron can call it with an absolute path).
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Load the webhook from .env (NOT committed to git). Format of .env:
#   DISCORD_WEBHOOK=https://discord.com/api/webhooks/XXXX/YYYY
if [[ -f "$DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$DIR/.env"
  set +a
fi

# Use the project venv if it exists, otherwise system python3.
if [[ -x "$DIR/.venv/bin/python" ]]; then
  PY="$DIR/.venv/bin/python"
else
  PY="python3"
fi

exec "$PY" "$DIR/monitor_once.py"
