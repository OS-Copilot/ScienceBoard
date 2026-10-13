#!/bin/bash
S="sudo -S -p ''"
echo 'deb http://ports.ubuntu.com/ubuntu-ports jammy-proposed main restricted universe multiverse' > /tmp/proposed.list
echo password | $S cp /tmp/proposed.list /etc/apt/sources.list.d/proposed.list
echo password | $S apt-get update -o Acquire::Retries=5 2>&1 | grep -E '^(Err|E:)' | head -3
apt-cache policy libicu-dev libicu70 | grep -E '^[a-z]|Candidate|Installed|ubuntu1|proposed' | head -10
if apt-cache show libicu-dev=70.1-2ubuntu1 >/dev/null 2>&1; then
  echo password | $S apt-get install -y libicu-dev=70.1-2ubuntu1 2>&1 | tail -1
else
  echo "proposed has no libicu-dev 70.1-2ubuntu1 for arm64; downgrading libicu70 to 70.1-2"
  echo password | $S apt-get install -y --allow-downgrades libicu70=70.1-2 libicu-dev=70.1-2 2>&1 | tail -2
fi
dpkg -l libicu70 libicu-dev | awk '/^ii/{print $2, $3}'
pgrep -f grass-source-build.sh >/dev/null && echo script-running || echo script-stopped
