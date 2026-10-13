#!/bin/bash
# ScienceBoard Celestia layer for the ARM VM: build the ShiinaHiiragi/Celestia
# fork (Qt6 frontend with an embedded HTTP state server, port = argv[1]) and
# CelestiaContent into the /app prefix, matching the reference VM layout
# (/app/bin/celestia-qt6). Qt 6.2.4 from Ubuntu 22.04 is used; the fork's Qt6
# CMake asks only for Core/Widgets/OpenGLWidgets without a minimum version.
set -uxo pipefail
export DEBIAN_FRONTEND=noninteractive
retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep $((n*15)); done; }
sudo_() { echo password | sudo -S -p '' "$@"; }
retry sudo_ apt-get install -y -o Acquire::Retries=5 build-essential cmake ninja-build gperf gettext pkg-config git \
  libboost-dev libepoxy-dev libjpeg-dev libpng-dev libgl1-mesa-dev libglu1-mesa-dev libgl-dev libeigen3-dev libfmt-dev \
  libfreetype6-dev libluajit-5.1-dev qt6-base-dev qt6-base-dev-tools qt6-base-private-dev libqt6opengl6-dev \
  qt6-tools-dev qt6-tools-dev-tools qt6-l10n-tools || exit 1
cd /home/user && { [ -d celestia-src/.git ] || retry git clone --depth 1 https://github.com/ShiinaHiiragi/Celestia celestia-src; } || exit 1
cd /home/user && { [ -d celestia-content/.git ] || retry git clone --depth 1 https://github.com/CelestiaProject/CelestiaContent celestia-content; } || exit 1
cmake -S /home/user/celestia-src -B /home/user/celestia-build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_QT5=OFF -DENABLE_QT6=ON -DENABLE_GTK=OFF -DENABLE_WIN=OFF -DENABLE_NLS=ON \
  -DCMAKE_INSTALL_PREFIX=/app || exit 1
cmake --build /home/user/celestia-build -j 8 || exit 1
sudo_ cmake --install /home/user/celestia-build || exit 1
cmake -S /home/user/celestia-content -B /home/user/celestia-content/build -DCMAKE_INSTALL_PREFIX=/app || exit 1
sudo_ cmake --build /home/user/celestia-content/build --target install || exit 1
sudo_ mkdir -p /home/user/6.5.0/gcc_64/lib; sudo_ chown -R user:user /home/user/6.5.0
ls -la /app/bin; du -sh /app
echo CELESTIA_VM_SETUP_DONE
