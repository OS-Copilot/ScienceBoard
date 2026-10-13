#!/usr/bin/env bash
# Unattended smoke test of the ScienceBoard VM pipeline against the ARM VM:
# one task per application family in --debug mode. Debug mode asks for a manual
# stop type on stdin; feeding empty lines selects TIMEOUT, so every task runs
# initialization (snapshot revert, boot, app launch, task setup) and evaluation
# without any model call. Expected result: all tasks fail with TIMEOUT and zero
# tasks skipped (a skip means initialization itself broke).
set -u
cd "$(dirname "$0")/../.."
tasks=(
  tasks/VM/Lean/A-01.json
  tasks/VM/TeXstudio/B-01.json
  tasks/VM/GrassGIS/A-01.json
  tasks/VM/Celestia/A-01.json
  tasks/VM/KAlgebra/A-01.json
)
logs=${1:-logs/debug-vm-smoke}
for t in "${tasks[@]}"; do
  echo "=== $t"
  yes '' 2>/dev/null | OPENAI_API_KEY=dummy ./run.sh --mode vm --model gpt_4o --debug --tasks "$t" --logs "$logs" --no-ignore 2>&1 | grep -E 'Task finished|total tested|Traceback|Error|skipped' | tail -5 || true
done
echo "=== results"
for f in "$logs"/*/result.out; do printf '%s: ' "$f"; cat "$f"; echo; done
