#!/bin/bash
# ScienceBoard GRASS GIS layer for the ARM VM: GRASS 8.4.x from ubuntugis-unstable
# (arm64 builds exist), the ShiinaHiiragi/grass-gui fork that exposes GUI state on
# FLASK_PORT, and the sample locations the tasks open:
#   /home/user/grassdata/world_latlong_wgs84      (startup location passed to `grass --gui`)
#   /home/user/grassdata/natural_earth_dataset    (countries@PERMANENT, ...)
#   /home/user/grassdata/grassdata_piemonte_utm32n_wgs84_grass7
# The two hand-placed points of the reference VM (task D-04) are not reproduced.
set -uxo pipefail
export DEBIAN_FRONTEND=noninteractive
retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep $((n*15)); done; }
sudo_() { echo password | sudo -S -p '' "$@"; }
sudo_ add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable
retry sudo_ apt-get update -o Acquire::Retries=5 || exit 1
retry sudo_ apt-get install -y -o Acquire::Retries=5 grass grass-gui git unzip || exit 1
grass --version | head -1
GUI_DIR=$(ls -d /usr/lib/grass8*/gui/wxpython | head -1); echo "GUI_DIR=$GUI_DIR"
if [ ! -f "$GUI_DIR/.scienceboard-fork" ]; then
  rm -rf /tmp/grass-gui; retry git clone --depth 1 https://github.com/ShiinaHiiragi/grass-gui /tmp/grass-gui || exit 1
  sudo_ mv "$GUI_DIR" "$GUI_DIR.orig"
  sudo_ mv /tmp/grass-gui "$GUI_DIR"
  sudo_ touch "$GUI_DIR/.scienceboard-fork"
fi
mkdir -p /home/user/grassdata /tmp/grass-dl && cd /tmp/grass-dl
fetch() { retry curl -sSL --retry 5 --retry-all-errors -o "$1" "$2"; }
fetch worldlocation.tar.gz https://grass.osgeo.org/sampledata/worldlocation.tar.gz || exit 1
fetch piemonte.tar.gz https://grass.osgeo.org/sampledata/grassdata_piemonte_utm32n_wgs84_grass7.tar.gz || exit 1
fetch natural_earth_dataset.zip "https://zenodo.org/records/13370131/files/natural_earth_dataset.zip?download=1" || exit 1
place() { # place <archive> <target-location-name>
  local arc="$1" name="$2" tmp="/tmp/grass-dl/x-$2"; rm -rf "$tmp"; mkdir -p "$tmp"
  case "$arc" in *.zip) unzip -q "$arc" -d "$tmp";; *) tar -xzf "$arc" -C "$tmp";; esac
  local loc; loc=$(dirname "$(find "$tmp" -maxdepth 3 -type d -name PERMANENT | head -1)")
  [ -d "$loc/PERMANENT" ] || { echo "no PERMANENT mapset in $arc"; return 1; }
  rm -rf "/home/user/grassdata/$name"; mv "$loc" "/home/user/grassdata/$name"
}
place worldlocation.tar.gz world_latlong_wgs84 || exit 1
place piemonte.tar.gz grassdata_piemonte_utm32n_wgs84_grass7 || exit 1
place natural_earth_dataset.zip natural_earth_dataset || exit 1
rm -rf /home/user/grassdata/*/*/.gislock; ls /home/user/grassdata; du -sh /home/user/grassdata
echo GRASS_VM_SETUP_DONE
