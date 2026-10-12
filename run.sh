#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
venv_python="$project_dir/.venv/bin/python"
local_elan_bin="$project_dir/.tools/elan-root/usr/bin"

if [[ ! -x "$venv_python" ]]; then
    echo "ScienceBoard environment is missing. Create .venv and install requirements first." >&2
    exit 2
fi

if [[ -x "$local_elan_bin/lake" ]]; then
    export ELAN_HOME="$project_dir/.tools/elan-home"
    export PATH="$local_elan_bin:$PATH"
fi

cd "$project_dir"
exec "$venv_python" main.py "$@"
