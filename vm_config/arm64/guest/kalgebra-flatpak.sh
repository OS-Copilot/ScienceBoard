#!/bin/bash
# ScienceBoard KAlgebra layer for the ARM VM. The ShiinaHiiragi/kalgebra fork
# needs KF6 >= 6.3 + Qt6 + Analitza6, which Ubuntu 22.04 does not package, so it
# is built as a Flatpak against org.kde.Platform 6.7 (aarch64 runtime exists).
# The fork embeds an HTTP state server on the port given as argv[1] (default
# 8000); the sandbox gets --share=network so the host-side runner can reach it.
# Tasks launch `LD_LIBRARY_PATH=/home/user/6.5.0/gcc_64/lib /app/bin/kalgebra <port>`,
# so /app/bin/kalgebra becomes a wrapper around `flatpak run`.
set -uxo pipefail
export DEBIAN_FRONTEND=noninteractive
retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 8 ] && return 1; sleep $((n*20)); done; }
sudo_() { echo password | sudo -S -p '' "$@"; }
retry sudo_ apt-get install -y -o Acquire::Retries=5 flatpak flatpak-builder git || exit 1
retry flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo || exit 1
retry flatpak install --user -y --noninteractive flathub org.kde.Platform//6.7 org.kde.Sdk//6.7 || exit 1
# KAlgebra's manifest builds on the QtWebEngine BaseApp; use the branch matching the runtime.
retry flatpak install --user -y --noninteractive flathub io.qt.qtwebengine.BaseApp//6.7 || exit 1
cd /home/user && { [ -d kalgebra/.git ] || retry git clone --depth 1 https://github.com/ShiinaHiiragi/kalgebra; } || exit 1
cd /home/user/kalgebra
# The fork's src/CMakeLists.txt bundles KF6/Qt libraries from ~/kde/usr and
# ~/6.5.0/gcc_64 with patchelf for the deb layout. Inside the Flatpak sandbox
# those paths do not exist and the runtime already provides the libraries, so
# that install step is skipped when flatpak-builder (FLATPAK_DEST) is building.
python3 - <<'PY'
import re
p = "src/CMakeLists.txt"; s = open(p, encoding="utf-8").read()
if "FLATPAK_DEST" not in s:
    s = s.replace('message(FATAL_ERROR "PATCHELF NOT FOUND; RUN `apt install patchelf` FIRST")',
                  'message(STATUS "PATCHELF NOT FOUND; bundling step is skipped under Flatpak")')
    i = s.index('install(CODE "set(BIN_DIR')
    s = s[:i] + "if(NOT DEFINED ENV{FLATPAK_DEST})\n" + s[i:].rstrip() + "\nendif()\n"
    open(p, "w", encoding="utf-8").write(s)
print("CMakeLists patched for Flatpak:", "FLATPAK_DEST" in open(p).read())
# The embedded HTTP server uses std::uint16_t without <cstdint>; newer libstdc++
# (KDE 6.7 SDK) no longer includes it transitively.
for f in ("src/uri.h", "src/http_server.h", "src/http_server.cpp"):
    c = open(f, encoding="utf-8").read()
    if "#include <cstdint>" not in c:
        open(f, "w", encoding="utf-8").write("#include <cstdint>\n" + c)
print("cstdint includes added")
PY
python3 - <<'PY'
import json
m = json.load(open(".flatpak-manifest.json"))
m["base-version"] = m.get("runtime-version", "6.7")
# The fork reads Analitza::PlotsModel::m_items/m_resolution, which upstream keeps
# private (the author's build instructions say to edit the installed header), so
# the analitza module exposes them after installing its headers in the sandbox.
for mod in m.get("modules", []):
    # The fork's CMake no longer installs the desktop file, but flatpak-builder
    # rewrites org.kde.kalgebra.desktop (rename-icon/copy-icon) and needs it.
    if isinstance(mod, dict) and mod.get("name") == "kalgebra":
        mod.setdefault("post-install", []).append("install -Dm644 /run/build/kalgebra/src/org.kde.kalgebra.desktop /app/share/applications/org.kde.kalgebra.desktop")
    if isinstance(mod, dict) and mod.get("name") == "analitza":
        mod["post-install"] = ["find /app/include -name plotsmodel.h -exec sed -i 's/^\\(\\s*\\)private:/\\1public:/' {} +"]
fa = m.setdefault("finish-args", [])
if "--share=network" not in fa:
    fa.append("--share=network")
json.dump(m, open("/home/user/kalgebra/flatpak-manifest.arm64.json", "w"), indent=2)
PY
retry flatpak-builder --user --install --force-clean /home/user/kalgebra-build /home/user/kalgebra/flatpak-manifest.arm64.json || exit 1
sudo_ mkdir -p /app/bin /home/user/6.5.0/gcc_64/lib
printf '#!/bin/sh\nexec flatpak run --share=network org.kde.kalgebra "$@"\n' > /tmp/kalgebra-wrapper
sudo_ install -m 755 /tmp/kalgebra-wrapper /app/bin/kalgebra
flatpak list --user | grep -i kalgebra
echo KALGEBRA_VM_SETUP_DONE
