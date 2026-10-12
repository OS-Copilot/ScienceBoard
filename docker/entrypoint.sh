#!/usr/bin/env bash
set -Eeuo pipefail

display_number="${DISPLAY#:}"
display_number="${display_number%%.*}"
runtime_dir="${XDG_RUNTIME_DIR:-/run/user/1000}"

cleanup() {
    local status=$?
    trap - EXIT INT TERM
    jobs -pr | xargs -r kill 2>/dev/null || true
    wait 2>/dev/null || true
    exit "$status"
}
trap cleanup EXIT INT TERM

install -d -m 0700 -o user -g user "$runtime_dir"
install -d -m 0755 /run/dbus /tmp/.X11-unix
rm -f "/tmp/.X${display_number}-lock" "/tmp/.X11-unix/X${display_number}"

rm -f /etc/machine-id /var/lib/dbus/machine-id
dbus-uuidgen --ensure=/etc/machine-id
install -d /var/lib/dbus
ln -s /etc/machine-id /var/lib/dbus/machine-id
dbus-daemon --system --fork --nopidfile

Xvfb "$DISPLAY" \
    -screen 0 1280x800x24 \
    -dpi 96 \
    -ac \
    +extension GLX \
    +render \
    -noreset \
    >/tmp/scienceboard-xvfb.log 2>&1 &

for _ in $(seq 1 100); do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        break
    fi
    if ! kill -0 "$!" 2>/dev/null; then
        echo "Xvfb exited before the display became ready" >&2
        cat /tmp/scienceboard-xvfb.log >&2 || true
        exit 1
    fi
    sleep 0.1
done
xdpyinfo -display "$DISPLAY" >/dev/null

exec setpriv \
    --reuid=1000 \
    --regid=1000 \
    --init-groups \
    --reset-env \
    env \
        DISPLAY="$DISPLAY" \
        HOME=/home/user \
        USER=user \
        LOGNAME=user \
        SHELL=/bin/bash \
        LANG=en_US.UTF-8 \
        LANGUAGE=en_US: \
        LC_NUMERIC=zh_CN.UTF-8 \
        LC_TIME=zh_CN.UTF-8 \
        LC_MONETARY=zh_CN.UTF-8 \
        LC_PAPER=zh_CN.UTF-8 \
        LC_NAME=zh_CN.UTF-8 \
        LC_ADDRESS=zh_CN.UTF-8 \
        LC_TELEPHONE=zh_CN.UTF-8 \
        LC_MEASUREMENT=zh_CN.UTF-8 \
        LC_IDENTIFICATION=zh_CN.UTF-8 \
        PATH=/home/user/bin:/home/user/.local/bin:/home/user/.elan/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
        XDG_RUNTIME_DIR="$runtime_dir" \
        XDG_SESSION_TYPE=x11 \
        NO_AT_BRIDGE=0 \
        QT_ACCESSIBILITY=1 \
        LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}" \
        GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}" \
        SCIENCEBOARD_SERVER_PORT="${SCIENCEBOARD_SERVER_PORT:-5000}" \
        /usr/local/bin/scienceboard-session
