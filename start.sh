#!/usr/bin/env bash

# Resolve absolute directory of the project
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Detect Python interpreter (prefer virtualenv)
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON="$(command -v python3)"
else
    PYTHON="python"
fi

# Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/logs"
export PYTHONPATH="$SCRIPT_DIR"
export PYTHONUNBUFFERED=1

# Check if foreground mode requested
if [ "$1" == "--foreground" ] || [ "$1" == "-f" ]; then
    exec "$PYTHON" -u "$SCRIPT_DIR/main.py" --service all
else
    # Stop any duplicate running instances of this app for current user
    pkill -u "$(id -u)" -f "$SCRIPT_DIR/main.py" 2>/dev/null || true
    sleep 0.5

    # Run in background detached without terminal
    nohup "$PYTHON" -u "$SCRIPT_DIR/main.py" --service all </dev/null >> "$SCRIPT_DIR/logs/app.log" 2>&1 &
    PID=$!
    disown $PID
    echo "Local ASR started in background (PID: $PID). Logs: $SCRIPT_DIR/logs/app.log"
fi
