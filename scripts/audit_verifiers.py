#!/usr/bin/env python3
"""Statically audit every ScienceBoard VM task/verifier configuration."""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


VERIFIERS = {
    "Celestia": {"info"},
    "ChimeraX": {"states", "info", "file"},
    "GrassGIS": {"info", "db"},
    "KAlgebra": {"val", "var", "eqn"},
    "Lean": {"placeholder"},
    "TeXstudio": {"compile", "file", "include"},
}

COMMON_INITIALIZERS = {"execute", "launch", "opt", "touch", "download", "append"}
APP_INITIALIZERS = {
    "Celestia": set(),
    "ChimeraX": {"destroy", "open", "turn", "alphafold_match", "color", "clear_log"},
    "GrassGIS": {"cmd", "map", "layer", "scale"},
    "KAlgebra": {"tab", "func_2d", "func_3d"},
    "Lean": {"import", "open", "def", "query"},
    "TeXstudio": {"chimerax_open", "chimerax_turn", "chimerax_clear_log"},
}


def require(condition: bool, errors: list[str], path: Path, message: str) -> None:
    if not condition:
        errors.append(f"{path}: {message}")


def check_lambda(value: Any, errors: list[str], path: Path, field: str) -> None:
    require(isinstance(value, str), errors, path, f"{field} must be a string")
    if not isinstance(value, str):
        return
    try:
        tree = ast.parse(value, mode="eval")
    except SyntaxError as exc:
        errors.append(f"{path}: invalid {field}: {exc.msg}")
        return
    require(isinstance(tree.body, ast.Lambda), errors, path, f"{field} must be a lambda")


def audit_task(path: Path, errors: list[str], counts: Counter) -> tuple[str, str]:
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return "", ""

    for field in ("type", "sort", "steps", "instruction", "version", "initialize", "evaluate"):
        require(field in task, errors, path, f"missing {field}")
    app = task.get("type")
    require(app in VERIFIERS, errors, path, f"unknown application {app!r}")
    require(task.get("sort") == "VM", errors, path, "Docker suite must use VM-sort tasks")
    require(isinstance(task.get("steps"), int) and task.get("steps", 0) > 0,
            errors, path, "steps must be a positive integer")
    require(isinstance(task.get("initialize"), list), errors, path, "initialize must be a list")
    require(isinstance(task.get("evaluate"), list) and len(task.get("evaluate", [])) > 0,
            errors, path, "evaluate must be a non-empty list")

    initializers = task.get("initialize", [])
    touches = {
        item.get("path"): item.get("text")
        for item in initializers
        if isinstance(item, dict) and item.get("func") == "touch"
    }
    for item in initializers:
        require(isinstance(item, dict) and isinstance(item.get("func"), str),
                errors, path, "each initializer needs a string func")
        if isinstance(item, dict) and isinstance(item.get("func"), str):
            allowed = COMMON_INITIALIZERS | APP_INITIALIZERS.get(app, set())
            require(item["func"] in allowed, errors, path,
                    f"unknown initializer {item['func']!r} for {app}")

    for item in task.get("evaluate", []):
        require(isinstance(item, dict), errors, path, "verifier must be an object")
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        counts[(app, kind)] += 1

        if kind == "stop":
            require(item.get("value") in {"ANS", "DONE", "FAIL", "TIMEOUT"},
                    errors, path, "stop verifier has an invalid value")
            if item.get("value") == "ANS":
                require(isinstance(item.get("args"), list)
                        and all(isinstance(arg, str) for arg in item["args"]),
                        errors, path, "ANS stop verifier needs string args")
            if task.get("ans") is not None:
                expected_answer = item.get("value", "")
                if item.get("args"):
                    expected_answer += " " + " ".join(item["args"])
                require(task["ans"] == expected_answer, errors, path,
                        "ans metadata disagrees with stop verifier")
            continue

        require(app in VERIFIERS and kind in VERIFIERS.get(app, set()),
                errors, path, f"unsupported verifier {kind!r} for {app}")

        if app == "Celestia" and kind == "info":
            check_lambda(item.get("key"), errors, path, "info.key")
            require("value" in item, errors, path, "info verifier needs value")
            if "pred" in item:
                check_lambda(item["pred"], errors, path, "info.pred")

        elif app == "GrassGIS" and kind in {"info", "db"}:
            check_lambda(item.get("key"), errors, path, f"{kind}.key")
            require("value" in item, errors, path, f"{kind} verifier needs value")
            if "pred" in item:
                check_lambda(item["pred"], errors, path, f"{kind}.pred")
            if kind == "db":
                require(isinstance(item.get("cmd"), str), errors, path, "db.cmd missing")
                require(isinstance(item.get("kwargs"), dict), errors, path, "db.kwargs missing")

        elif app == "ChimeraX":
            require(isinstance(item.get("key"), str), errors, path, f"{kind}.key missing")
            if kind == "states":
                require("value" in item or "pattern" in item,
                        errors, path, "states verifier needs value or pattern")
                if str(item.get("key", "")).startswith("lambda"):
                    check_lambda(item["key"], errors, path, "states.key")
                if "find" in item:
                    check_lambda(item["find"], errors, path, "states.find")
                if "pattern" in item:
                    try:
                        re.compile(item["pattern"])
                    except (TypeError, re.error) as exc:
                        errors.append(f"{path}: invalid states.pattern: {exc}")
            elif kind == "info":
                require(isinstance(item.get("value"), list)
                        and all(isinstance(line, str) for line in item["value"]),
                        errors, path, "info.value must be a string list")
            elif kind == "file":
                require(isinstance(item.get("value"), str),
                        errors, path, "file.value must be a string")

        elif app == "KAlgebra":
            require("key" in item and "value" in item,
                    errors, path, f"{kind} verifier needs key and value")

        elif app == "Lean":
            require(kind == "placeholder", errors, path, "Lean verifier must be placeholder")

        elif app == "TeXstudio":
            guest_path = item.get("path")
            require(isinstance(guest_path, str), errors, path, f"{kind}.path missing")
            if kind == "compile":
                require(isinstance(item.get("file"), str), errors, path, "compile.file missing")
            elif kind == "include":
                try:
                    re.compile(item.get("pattern", ""))
                except (TypeError, re.error) as exc:
                    errors.append(f"{path}: invalid include.pattern: {exc}")
            elif kind == "file":
                require(guest_path in touches, errors, path,
                        "file verifier path has no matching touch initializer")
                if "source" in item or "target" in item:
                    require("source" in item and "target" in item,
                            errors, path, "file replacement needs source and target")
                    before = touches.get(guest_path)
                    if isinstance(before, str) and isinstance(item.get("source"), str):
                        require(before.count(item["source"]) == 1, errors, path,
                                "file verifier source must occur exactly once")

    if app == "Lean":
        queries = [item for item in initializers if item.get("func") == "query"]
        require(len(queries) == 1, errors, path, "Lean task needs exactly one query")
        if len(queries) == 1:
            require(str(queries[0].get("expr", "")).endswith("by sorry"),
                    errors, path, "Lean query must end with 'by sorry'")

    return str(app), str(task.get("instruction", ""))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tasks", nargs="?", default="tasks/VM")
    args = parser.parse_args()
    root = Path(args.tasks)
    paths = sorted(root.rglob("*.json"))
    errors: list[str] = []
    counts: Counter = Counter()
    identities: Counter = Counter()

    for path in paths:
        identities[audit_task(path, errors, counts)] += 1
    duplicates = [identity for identity, count in identities.items() if count > 1]
    for app, instruction in duplicates:
        errors.append(f"duplicate instruction for {app}: {instruction}")

    report = {
        "task_root": str(root),
        "tasks_checked": len(paths),
        "verifiers_checked": sum(counts.values()),
        "counts": {
            f"{app}/{kind}": count
            for (app, kind), count in sorted(counts.items())
        },
        "errors": errors,
        "warnings": [
            "Task-authored lambda predicates execute on the host; task JSON is a trusted input boundary.",
            "Several ChimeraX state checks intentionally depend on version-specific serialized internals.",
            "Stop/ANS ground-truth correctness requires semantic review in addition to this structural audit.",
        ],
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
