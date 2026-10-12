#!/usr/bin/env python3
"""Create the deterministic 20-task Docker parity subset."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


TASKS = (
    "Celestia/A-01.json",
    "Celestia/A-03.json",
    "Celestia/C-03.json",
    "ChimeraX/A-01.json",
    "ChimeraX/A-04.json",
    "ChimeraX/C-07.json",
    "ChimeraX/D-03.json",
    "GrassGIS/A-01.json",
    "GrassGIS/A-09.json",
    "GrassGIS/B-02.json",
    "GrassGIS/D-01.json",
    "KAlgebra/A-01.json",
    "KAlgebra/A-04.json",
    "KAlgebra/B-01.json",
    "KAlgebra/C-01.json",
    "Lean/A-01.json",
    "Lean/C-01.json",
    "TeXstudio/A-04.json",
    "TeXstudio/B-04.json",
    "TeXstudio/C-03.json",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="tasks/VM")
    parser.add_argument("--output", default=".artifacts/smoke20")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    if len(TASKS) != 20 or len(set(TASKS)) != 20:
        raise RuntimeError("the smoke suite must contain exactly 20 unique tasks")

    missing = [name for name in TASKS if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing source tasks: {missing}")

    output.mkdir(parents=True, exist_ok=True)
    legacy_manifest = output / "manifest.lock"
    if legacy_manifest.exists():
        legacy_manifest.unlink()
    expected = set(TASKS)
    for stale in output.rglob("*.json"):
        if str(stale.relative_to(output)) not in expected:
            stale.unlink()

    manifest = []
    for name in TASKS:
        src = source / name
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        task = json.loads(src.read_text(encoding="utf-8"))
        manifest.append({
            "path": name,
            "application": task["type"],
            "verifiers": sorted({item["type"] for item in task["evaluate"]}),
        })

    manifest_path = output.parent / f"{output.name}-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
