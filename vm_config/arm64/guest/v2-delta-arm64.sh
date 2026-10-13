#!/bin/bash
# OSWorld-V2 application delta for the ARM VM, ported from xlang-ai/osworld_image
# (ansible/group_vars/all.yml + roles packages/chrome/x11/defaults/first_run).
# Only what has an arm64 build is installed; versions therefore differ from the
# x86 V2 image:
#   Obsidian 1.10.6 (arm64 AppImage), MuseScore Studio 4.6.0 (aarch64 AppImage),
#   REAPER 7.64 (linux-aarch64), Audacity/Blender/Shotcut/LabPlot from Ubuntu apt,
#   Node.js runtime, Chrome Safe Browsing policy, Xorg MaxClients, LibreOffice
#   MIME defaults, first-run state for MuseScore and REAPER.
# Not installed: XMind (no Linux arm64), Zotero 8.0.2 (no arm64 release), WPS
# Office (arm64 package URL not verified), zotero-snap.
# The osworld-server upgrade to the V2 pin (a3cc3f0, src/ layout) is a separate step.
set -uxo pipefail
export DEBIAN_FRONTEND=noninteractive
retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep $((n*15)); done; }
sudo_() { echo password | sudo -S -p '' "$@"; }
HOME_DIR=/home/user; APPDIR=/opt/osworld-appimages
retry sudo_ apt-get install -y -o Acquire::Retries=5 nodejs npm jq libfuse2 audacity blender shotcut labplot xdg-utils || exit 1
node --version; npm --version
sudo_ mkdir -p "$APPDIR" /usr/share/icons/hicolor/512x512/apps
fetch() { retry curl -sSL --retry 5 --retry-all-errors -o "$1" "$2"; }
fetch /tmp/Obsidian.AppImage https://github.com/obsidianmd/obsidian-releases/releases/download/v1.10.6/Obsidian-1.10.6-arm64.AppImage || exit 1
fetch /tmp/MuseScore.AppImage https://github.com/musescore/MuseScore/releases/download/v4.6.0/MuseScore-Studio-4.6.0.252730943-aarch64.AppImage || exit 1
fetch /tmp/reaper.tar.xz https://dlcf.reaper.fm/7.x/reaper764_linux_aarch64.tar.xz || exit 1
sudo_ install -m 755 /tmp/Obsidian.AppImage "$APPDIR/obsidian-1.10.6.AppImage"
sudo_ install -m 755 /tmp/MuseScore.AppImage "$APPDIR/musescore-4.6.0.AppImage"
sudo_ ln -sf "$APPDIR/obsidian-1.10.6.AppImage" /usr/local/bin/obsidian
sudo_ ln -sf "$APPDIR/musescore-4.6.0.AppImage" /usr/local/bin/musescore
desktop() { printf '[Desktop Entry]\nType=Application\nName=%s\nExec=%s %%U\nIcon=%s\nCategories=%s\nTerminal=false\n' "$1" "$2" "$3" "$4" | sudo_ tee "/usr/share/applications/$5.desktop" >/dev/null; }
desktop Obsidian /usr/local/bin/obsidian obsidian "Office;Utility;" obsidian
desktop "MuseScore Studio" /usr/local/bin/musescore musescore "Audio;Music;Education;" musescore
mkdir -p /tmp/reaper && tar -xJf /tmp/reaper.tar.xz -C /tmp/reaper --strip-components=1 && sudo_ /tmp/reaper/install-reaper.sh --install /opt --integrate-desktop --usr-local-bin-symlink --quiet
echo '{"SafeBrowsingProtectionLevel": 0, "SafeBrowsingEnabled": false}' | sudo_ tee /etc/opt/chrome/policies/managed/osworld-safe-browsing.json >/dev/null 2>&1 || { sudo_ mkdir -p /etc/opt/chrome/policies/managed; echo '{"SafeBrowsingProtectionLevel": 0, "SafeBrowsingEnabled": false}' | sudo_ tee /etc/opt/chrome/policies/managed/osworld-safe-browsing.json >/dev/null; }
mkdir -p "$HOME_DIR/.config/google-chrome/Default"; pref="$HOME_DIR/.config/google-chrome/Default/Preferences"; if [ -s "$pref" ]; then jq '.safebrowsing.enabled=false | .safebrowsing.enhanced=false' "$pref" > /tmp/pref.json && cat /tmp/pref.json > "$pref"; else printf '{"safebrowsing":{"enabled":false,"enhanced":false}}\n' > "$pref"; fi; chmod 600 "$pref"
sudo_ sh -c 'touch /etc/X11/xorg.conf; grep -q MaxClients /etc/X11/xorg.conf || printf "\nSection \"ServerFlags\"\n    Option \"MaxClients\" \"2048\"\nEndSection\n" >> /etc/X11/xorg.conf'
for m in application/msword application/vnd.openxmlformats-officedocument.wordprocessingml.document application/vnd.oasis.opendocument.text; do xdg-mime default libreoffice-writer.desktop $m; done
for m in application/vnd.ms-excel application/vnd.openxmlformats-officedocument.spreadsheetml.sheet application/vnd.oasis.opendocument.spreadsheet; do xdg-mime default libreoffice-calc.desktop $m; done
for m in application/vnd.ms-powerpoint application/vnd.openxmlformats-officedocument.presentationml.presentation application/vnd.oasis.opendocument.presentation; do xdg-mime default libreoffice-impress.desktop $m; done
mkdir -p "$HOME_DIR/.config/MuseScore" "$HOME_DIR/.local/share/MuseScore/MuseScore4/session" "$HOME_DIR/.config/REAPER"
printf '[application]\nhasCompletedFirstLaunchSetup=true\nskippedVersion=4.6.5\n' > "$HOME_DIR/.config/MuseScore/MuseScore4.ini"; printf '[]\n' > "$HOME_DIR/.local/share/MuseScore/MuseScore4/session/session.json"
printf '[.swell]\nui_scale=1.0\nui_scale_auto=1\n\n[nag]\nnag=968F066A9E622BB184F6F6CEC305F00653DAD4DDB598FF1BB2\n\n[reaper]\nlastproject=\n\n[verchk]\nlastt=4102444800\n' > "$HOME_DIR/.config/REAPER/reaper.ini"
printf '[us]\nuss=958F066A1B000000020000000000000000000000C3E82552AF74DC738D754B01FD7AB4CFC08D3DDCF3\n' > "$HOME_DIR/.config/REAPER/reaper-reginfo2.ini"
ls -la "$APPDIR" /opt/REAPER 2>/dev/null | head; dpkg -l audacity blender shotcut labplot | awk '/^ii/{print $2, $3}'
echo V2_DELTA_DONE
