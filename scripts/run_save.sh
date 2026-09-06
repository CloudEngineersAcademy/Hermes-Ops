#!/bin/bash
# Hermes Ops — Scheduled Save Wrapper
# Runs the Python save_session.py with the GITHUB_TOKEN in the environment.
#
# Schedule: every 3 hours (adjust as needed)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_OPS_DIR="/Users/user/Hermes-Ops"

# Load token from .env (not committed to repo)
if [ -f "$HERMES_OPS_DIR/.env" ]; then
    export $(grep -v '^#' "$HERMES_OPS_DIR/.env" | xargs)
fi

export GITHUB_TOKEN

/usr/bin/python3 "$HERMES_OPS_DIR/scripts/save_session.py" >> "$HERMES_OPS_DIR/save.log" 2>&1
