#!/bin/sh
set -eu
umask 077
: "${WORKSPACE_USER:?Set WORKSPACE_USER in service variables}"
: "${WORKSPACE_PASSWORD:?Set WORKSPACE_PASSWORD in service variables}"
: "${WORKSPACE_API_KEY:?Set WORKSPACE_API_KEY in service variables}"
if [ -n "${RAILWAY_ENVIRONMENT_ID:-}" ] && [ "${RAILWAY_VOLUME_MOUNT_PATH:-}" != /var/data ]; then
    echo 'Attach a persistent Railway volume at /var/data before starting.' >&2
    exit 1
fi
if [ -n "${FLY_APP_NAME:-}" ] && ! mountpoint -q /var/data; then
    echo 'Attach the edgeboard_data Fly volume at /var/data before starting.' >&2
    exit 1
fi
if [ "$(id -u)" = 0 ]; then
    # Hosted volumes may be root-owned. Initialize only the mount directory,
    # then drop privileges before either application server starts.
    [ -d /var/data ] && [ ! -L /var/data ]
    chown --no-dereference 10001:10001 /var/data
    exec setpriv --reuid=10001 --regid=10001 --init-groups -- sh "$0"
fi
exec python next_app/server.py --host 0.0.0.0 --port "${PORT:-10000}" --data-dir /var/data --require-research
