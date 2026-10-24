#!/bin/sh
set -eu
umask 077
: "${WORKSPACE_USER:?Set WORKSPACE_USER in Render Environment}"
: "${WORKSPACE_PASSWORD:?Set WORKSPACE_PASSWORD in Render Environment}"
exec python next_app/server.py --host 0.0.0.0 --port "${PORT:-10000}" --data-dir /var/data
