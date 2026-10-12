#!/usr/bin/env bash
set -Eeuo pipefail

# Ubuntu 22.04's /usr/bin/firefox is only a snapd shim. Containers do not run
# snapd, so the Docker build extracts the exact bundled Firefox snap and this
# wrapper supplies the small runtime environment that its launcher expects.
firefox_root=/opt/firefox-snap
revision="$(cat "$firefox_root/.scienceboard-revision")"

export SNAP="$firefox_root"
export SNAP_NAME=firefox
export SNAP_INSTANCE_NAME=firefox
export SNAP_REVISION="$revision"
export SNAP_ARCH=amd64
export SNAP_REAL_HOME="${HOME:-/home/user}"
export SNAP_USER_COMMON="$SNAP_REAL_HOME/snap/firefox/common"
export SNAP_USER_DATA="$SNAP_REAL_HOME/snap/firefox/$revision"
export GTK_USE_PORTAL=0

mkdir -p "$SNAP_USER_COMMON" "$SNAP_USER_DATA"
exec "$SNAP/firefox.launcher" "$@"
