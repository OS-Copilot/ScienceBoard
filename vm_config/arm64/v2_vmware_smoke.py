#!/usr/bin/env python3
"""Run OSWorld-V2 tasks on the unified ARM VM through the VMware provider.

Usage (from the OSWorld-V2 checkout, with its venv):
    OSWORLD_FILE_BASE_URL=$PWD/cache/osworld_v2_assets_v2.1 \
    .venv/bin/python <this file> --vmx <Ubuntu.vmx> --tasks 001 002 [--snapshot sci_bench]

With no agent, every task runs setup on a fresh `sci_bench` revert, takes zero
actions, and is evaluated. The expected outcome of a healthy environment is a
score of 0 (or the task's "infeasible" handling) without exceptions; an
exception in setup or evaluate means the client image lacks something the task
needs (app, website, GitLab, or asset).
"""
import argparse
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.getcwd())
from desktop_env.desktop_env import DesktopEnv  # noqa: E402
from task_loader import load_task_config, resolve_task_json_path  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vmx", required=True)
    ap.add_argument("--tasks", nargs="+", required=True, help="task ids such as 001")
    ap.add_argument("--snapshot", default="sci_bench")
    ap.add_argument("--client_password", default="password")
    ap.add_argument("--base_dir", default="evaluation_examples")
    ap.add_argument("--out", default="results_v2_vmware_smoke")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    env = DesktopEnv(
        provider_name="vmware", path_to_vm=args.vmx, snapshot_name=args.snapshot,
        action_space="pyautogui", headless=True, os_type="Ubuntu",
        require_a11y_tree=False, client_password=args.client_password,
    )
    summary = {}
    try:
        for task_id in args.tasks:
            rec = {"task": task_id}
            t0 = time.time()
            try:
                config_file = resolve_task_json_path(task_id=task_id, base_dir=args.base_dir, domain="tasks", eval_version="v2")
                example = load_task_config(config_file, task_id=task_id, base_dir=args.base_dir, domain="tasks", eval_version="v2")
                rec["instruction"] = str(example.get("instruction", ""))[:160]
                env.reset(task_config=example)
                rec["reset_s"] = round(time.time() - t0, 1)
                result = env.evaluate()
                rec["result"] = result if isinstance(result, (int, float)) else (result.get("score") if isinstance(result, dict) else str(result)[:80])
                rec["status"] = "ok"
            except Exception as exc:  # noqa: BLE001
                rec["status"] = "error"
                rec["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
                rec["traceback"] = traceback.format_exc()[-1500:]
            rec["total_s"] = round(time.time() - t0, 1)
            summary[task_id] = rec
            print(json.dumps({k: v for k, v in rec.items() if k != "traceback"}, ensure_ascii=False), flush=True)
    finally:
        env.close()
    json.dump(summary, open(os.path.join(args.out, "summary.json"), "w"), indent=2, ensure_ascii=False)
    errors = [t for t, r in summary.items() if r["status"] != "ok"]
    print(f"done: {len(summary)} tasks, {len(errors)} with errors: {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
