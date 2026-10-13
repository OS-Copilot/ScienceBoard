#!/bin/bash
# ScienceBoard Lean layer for the ARM VM, following vm_config/manual.md:
# elan + Lean 4.14.0, a `sci` lake project under /home/user with Mathlib v4.14.0.
set -uxo pipefail
cd /home/user
retry() { local n=0; until "$@"; do n=$((n+1)); [ "$n" -ge 6 ] && return 1; sleep $((n*10)); done; }
if [ ! -x /home/user/.elan/bin/lake ]; then
  retry curl -sSf --retry 5 --retry-all-errors https://elan.lean-lang.org/elan-init.sh -o /tmp/elan-init.sh || exit 1
  retry sh /tmp/elan-init.sh -y --default-toolchain leanprover/lean4:v4.14.0 || exit 1
fi
export PATH=/home/user/.elan/bin:$PATH
grep -q '.elan/bin' /home/user/.bashrc || printf 'export PATH=/home/user/.elan/bin:$PATH\n' >> /home/user/.bashrc
grep -q '.elan/bin' /home/user/.profile || printf 'PATH=/home/user/.elan/bin:$PATH\n' >> /home/user/.profile
elan default leanprover/lean4:v4.14.0
[ -d /home/user/sci ] || lake new sci
cd /home/user/sci
if [ -f lakefile.toml ]; then
  grep -q 'name = "mathlib"' lakefile.toml || printf '\n[[require]]\nname = "mathlib"\nscope = "leanprover-community"\nrev = "v4.14.0"\n' >> lakefile.toml
else
  grep -q 'mathlib' lakefile.lean || printf '\nrequire mathlib from git "https://github.com/leanprover-community/mathlib4" @ "v4.14.0"\n' >> lakefile.lean
fi
retry lake update || exit 1
retry lake exe cache get || exit 1
retry lake build || exit 1
echo LEAN_VM_SETUP_DONE
