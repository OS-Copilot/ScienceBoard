#!/usr/bin/env bash
set -Eeuo pipefail

# Electron's Chromium sandbox cannot create its nested namespace in a regular
# unprivileged Docker container.  The container itself is already the sandbox
# boundary, so keep the task-authored ``code ...`` commands unchanged and add
# the required flags here. A basic password store avoids Electron racing the
# PAM-less GNOME session for the login keyring and opening a modal prompt in
# front of later applications.
exec /usr/bin/code --no-sandbox --disable-gpu --password-store=basic "$@"
