#!/bin/bash
# wxPython >= 4.2 for the ARM VM. GRASS 8.4's wx GUI refuses to start with
# Ubuntu 22.04's python3-wxgtk4.0 (4.0.7) and no arm64 wheel exists, so wxPython
# is built from the PyPI sdist (bundles wxWidgets 3.2) for the system Python 3.10.
# Installed with --user so the system package stays untouched; the user site
# takes precedence on sys.path.
set -uxo pipefail
export DEBIAN_FRONTEND=noninteractive
retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep $((n*15)); done; }
sudo_() { echo password | sudo -S -p '' "$@"; }
retry sudo_ apt-get install -y -o Acquire::Retries=5 build-essential python3-dev python3-pip libgtk-3-dev libwebkit2gtk-4.0-dev libnotify-dev libsdl2-dev \
  libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libjpeg-dev libpng-dev libtiff-dev libexpat1-dev libxtst-dev libgl1-mesa-dev libglu1-mesa-dev freeglut3-dev libsecret-1-dev || exit 1
# setuptools is pinned: wxPython 4.2.3's setup.py wraps distutils copy_file with an
# older signature and fails on setuptools >= 80 (TypeError: copy_file() ... 8 were given),
# while 4.2.3 imports setuptools.command.bdist_wheel, which exists only from 70.1;
# wheel is pinned too because setuptools 69 still imports wheel.bdist_wheel, removed in wheel 0.46.
python3 -m pip install --user --upgrade pip wheel attrdict3 requests sip typing_extensions "setuptools==70.3.0" "wheel==0.45.1" 2>&1 | tail -1
# --no-build-isolation: the isolated build env lacks typing_extensions, which
# wxPython's sip/etg code generation imports (ModuleNotFoundError otherwise).
export MAKEFLAGS="-j4"
retry python3 -m pip install --user --no-build-isolation --no-binary wxPython "wxPython==4.2.3" 2>&1 | tail -5 || exit 1
python3 -c 'import wx; print("wxPython", wx.version())' || exit 1
echo WXPYTHON_DONE
