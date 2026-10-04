#!/usr/bin/env bash
# oil-cover — one-time script-mode setup

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
VENV_DIR="$SKILL_DIR/.venv"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "ERROR: Python 3.9+ is required." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "ERROR: Python 3.9+ is required. Current version: $($PYTHON --version 2>&1)" >&2
    exit 1
fi

if [[ -n "${FFMPEG:-}" ]]; then
    if [[ ! -x "$FFMPEG" ]]; then
        echo "ERROR: FFMPEG does not point to an executable: $FFMPEG" >&2
        exit 1
    fi
elif command -v ffmpeg >/dev/null 2>&1; then
    FFMPEG="$(command -v ffmpeg)"
else
    for candidate in /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do
        if [[ -x "$candidate" ]]; then
            FFMPEG="$candidate"
            break
        fi
    done
fi

if [[ -z "${FFMPEG:-}" ]]; then
    echo "ERROR: ffmpeg is required. Install it, then run this setup again." >&2
    exit 1
fi

if [[ ! -x "$VENV_DIR/bin/python3" && ! -x "$VENV_DIR/bin/python" ]]; then
    "$PYTHON" -m venv "$VENV_DIR"
fi

if [[ -x "$VENV_DIR/bin/python3" ]]; then
    VENV_PYTHON="$VENV_DIR/bin/python3"
else
    VENV_PYTHON="$VENV_DIR/bin/python"
fi

"$VENV_PYTHON" -m pip install --quiet --upgrade pip
"$VENV_PYTHON" -m pip install --quiet -r "$SKILL_DIR/requirements.txt"
"$VENV_PYTHON" -c 'import numpy; from PIL import Image'

echo "oil-cover setup complete."
