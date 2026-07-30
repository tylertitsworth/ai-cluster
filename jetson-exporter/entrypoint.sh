#!/bin/sh
set -e

REQUIRED_SPEC=$(python3 /app/probe_version.py)
if [ -n "$REQUIRED_SPEC" ]; then
    echo "jtop client/service version mismatch detected, installing $REQUIRED_SPEC"
    pip install --quiet "$REQUIRED_SPEC"
fi

exec python3 /app/exporter.py --port 8000
