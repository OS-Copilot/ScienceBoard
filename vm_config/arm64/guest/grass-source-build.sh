#!/bin/bash
# GRASS GIS 8.4.2 from source for the ARM VM. The ubuntugis-unstable PPA publishes
# grass-core/grass-gui 8.4.2 only for amd64 (arm64 gets just the empty `grass`
# metapackage), so the Ubuntu 7.8 packages are purged and 8.4.2 is built into
# /usr/local/grass84 (launcher /usr/local/bin/grass). The ShiinaHiiragi/grass-gui
# fork then replaces gui/wxpython, as in vm_config/manual.md.
set -uxo pipefail
export DEBIAN_FRONTEND=noninteractive
retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep $((n*15)); done; }
sudo_() { echo password | sudo -S -p '' "$@"; }
sudo_ apt-get purge -y grass grass-core grass-gui grass-doc grass-dev 2>/dev/null; sudo_ apt-get autoremove -y
retry sudo_ apt-get install -y -o Acquire::Retries=5 build-essential flex bison make gcc g++ python3-dev python3-numpy python3-dateutil python3-pil python3-ply python3-six python3-wxgtk4.0 \
  libproj-dev proj-data proj-bin libgdal-dev gdal-bin libgeos-dev libsqlite3-dev sqlite3 libpng-dev libtiff5-dev libjpeg-dev libfftw3-dev libcairo2-dev libfreetype6-dev \
  libreadline-dev libncurses5-dev libbz2-dev zlib1g-dev libzstd-dev libglu1-mesa-dev libgl1-mesa-dev libxmu-dev gettext git unzip curl || exit 1
cd /home/user && { [ -d grass-8.4.2 ] || { retry curl -sSL --retry 5 --retry-all-errors -o grass-8.4.2.tar.gz https://github.com/OSGeo/grass/archive/refs/tags/8.4.2.tar.gz && tar -xzf grass-8.4.2.tar.gz; }; } || exit 1
cd /home/user/grass-8.4.2 || exit 1
./configure --with-cxx --enable-largefile --with-proj-share=/usr/share/proj --with-gdal=/usr/bin/gdal-config --with-python --with-geos=/usr/bin/geos-config \
  --with-sqlite --with-nls --with-fftw --with-cairo --with-freetype --with-freetype-includes=/usr/include/freetype2/ --with-readline --with-bzlib --with-zstd \
  --with-wxwidgets --with-openmp --with-opengl-libs=/usr/include/GL --without-pdal --without-netcdf --without-postgres --without-odbc > /home/user/grass-configure.log 2>&1 || { tail -30 /home/user/grass-configure.log; exit 1; }
make -j 8 > /home/user/grass-make.log 2>&1 || { grep -nE 'error|Error' /home/user/grass-make.log | tail -20; exit 1; }
sudo_ make install > /home/user/grass-install.log 2>&1 || { tail -20 /home/user/grass-install.log; exit 1; }
hash -r; /usr/local/bin/grass --version | head -1
GUI_DIR=/usr/local/grass84/gui/wxpython; [ -d "$GUI_DIR" ] || { echo "no $GUI_DIR"; ls /usr/local; exit 1; }
if [ ! -f "$GUI_DIR/.scienceboard-fork" ]; then
  rm -rf /tmp/grass-gui; retry git clone --depth 1 https://github.com/ShiinaHiiragi/grass-gui /tmp/grass-gui || exit 1
  sudo_ mv "$GUI_DIR" "$GUI_DIR.orig"; sudo_ mv /tmp/grass-gui "$GUI_DIR"; sudo_ touch "$GUI_DIR/.scienceboard-fork"
fi
rm -rf /home/user/grassdata/*/*/.gislock; which grass; ls "$GUI_DIR" | head -5
echo GRASS_SRC_SETUP_DONE
