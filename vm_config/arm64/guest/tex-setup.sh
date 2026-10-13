#!/bin/bash
# ScienceBoard TeXstudio layer for the ARM VM: TeXstudio from the sunderme PPA
# (arm64 builds exist for jammy) and TeX Live full instead of MiKTeX, so that
# /tex/check's /usr/bin/pdflatex and /usr/bin/bibtex exist and no package is
# ever missing. Runs as user; sudo password is the VM default.
set -uxo pipefail
export DEBIAN_FRONTEND=noninteractive
SUDO="sudo -S -p ''"
retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 5 ] && return 1; sleep $((n*15)); done; }
pw() { echo password; }
pw | $SUDO add-apt-repository -y ppa:sunderme/texstudio
retry sh -c "echo password | sudo -S -p '' apt-get update -o Acquire::Retries=5" || exit 1
retry sh -c "echo password | sudo -S -p '' apt-get install -y -o Acquire::Retries=5 texstudio texlive-full" || exit 1
mkdir -p /home/user/atelier
texstudio --version 2>/dev/null | head -1; pdflatex --version | head -1; bibtex --version | head -1
echo TEX_VM_SETUP_DONE
