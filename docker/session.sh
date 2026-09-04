#!/usr/bin/env bash
set -Eeuo pipefail

export DISPLAY="${DISPLAY:-:0}"
export HOME=/home/user
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export XDG_SESSION_TYPE=x11
export XDG_CURRENT_DESKTOP=ubuntu:GNOME
export XDG_SESSION_DESKTOP=ubuntu
export DESKTOP_SESSION=ubuntu
export GNOME_SHELL_SESSION_MODE=ubuntu
export NO_AT_BRIDGE=0
export QT_ACCESSIBILITY=1

cd "$HOME"

exec dbus-run-session -- bash -c '
    set -Eeuo pipefail
    dbus-update-activation-environment \
        DISPLAY HOME USER XDG_RUNTIME_DIR XDG_SESSION_TYPE \
        NO_AT_BRIDGE QT_ACCESSIBILITY \
        >/dev/null 2>&1 || true

    gsettings set org.gnome.desktop.interface toolkit-accessibility true \
        >/dev/null 2>&1 || true
    gsettings set org.gnome.desktop.session idle-delay 0 \
        >/dev/null 2>&1 || true
    gsettings set org.gnome.desktop.screensaver lock-enabled false \
        >/dev/null 2>&1 || true
    gsettings set org.gnome.desktop.lockdown disable-lock-screen true \
        >/dev/null 2>&1 || true
    gsettings set org.gnome.desktop.notifications show-banners false \
        >/dev/null 2>&1 || true

    # The reference VM uses Ubuntu GNOME.  Mutter works on Xvfb through Mesa
    # llvmpipe, preserving the Activities overview, Alt+F2 launcher, top bar,
    # window maximization, and other desktop interactions used by tasks.
    # Openbox remains a startup fallback for unusually constrained hosts.
    wm_ready=false
    if command -v gnome-shell >/dev/null 2>&1; then
        gnome-shell --x11 --replace >/tmp/scienceboard-gnome-shell.log 2>&1 &
        gnome_pid=$!
        for _ in $(seq 1 100); do
            if ! kill -0 "$gnome_pid" 2>/dev/null; then
                break
            fi
            if xprop -root _NET_SUPPORTING_WM_CHECK 2>/dev/null \
                    | grep -q "window id"; then
                wm_ready=true
                break
            fi
            sleep 0.1
        done
    fi
    if [[ "$wm_ready" != true ]]; then
        if [[ -n "${gnome_pid:-}" ]]; then
            kill "$gnome_pid" 2>/dev/null || true
        fi
        openbox --sm-disable >/tmp/scienceboard-openbox.log 2>&1 &
        xsetroot -solid "#2c2c2c" >/dev/null 2>&1 || true
    else
        # GNOME starts in Activities when no window is open.  Leave the
        # overview so task initializers receive a normal reference desktop.
        sleep 1
        /usr/bin/python -c \
            "import pyautogui; pyautogui.press('esc')" \
            >/dev/null 2>&1 || true
    fi

    # A normal GDM/PAM login unlocks the desktop login keyring. This direct
    # headless session has no PAM transaction, so unlock the reference user
    # keyring explicitly; otherwise Firefox opens behind a modal password
    # prompt. The benchmark image and prompts already use this fixed password.
    if command -v gnome-keyring-daemon >/dev/null 2>&1; then
        printf "password\n" | gnome-keyring-daemon --unlock \
            >/tmp/scienceboard-keyring.log 2>&1 || true
    fi

    # The service is normally D-Bus activated. Starting it explicitly makes
    # accessibility readiness deterministic on minimal cloud hosts.
    if [[ -x /usr/libexec/at-spi-bus-launcher ]]; then
        /usr/libexec/at-spi-bus-launcher --launch-immediately \
            >/tmp/scienceboard-atspi.log 2>&1 &
    fi

    exec /usr/bin/python /home/user/server/main.py
'
