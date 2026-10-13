#!/usr/bin/env python3
"""Append ScienceBoard's guest endpoints to an OSWorld server main.py.

Usage: merge_scienceboard_endpoints.py <osworld main.py> <scienceboard server.py> <output>

The ScienceBoard block (/opt, /read, /write, /append, /chimerax/run,
/lean/check, /tex/check) is taken verbatim from vm_config/server.py and
inserted before the `if __name__ == '__main__':` block of the OSWorld server,
so any pinned osworld-server commit can be re-merged the same way.
"""
import re
import sys


def main() -> int:
    base_path, sb_path, out_path = sys.argv[1:4]
    base = open(base_path, encoding="utf-8").read()
    sb = open(sb_path, encoding="utf-8").read()
    start = sb.index("# self-defined requests start from here")
    end = sb.index("if __name__ == '__main__':", start)
    block = sb[start:end].rstrip() + "\n\n"
    block = block.replace(
        "# self-defined requests start from here",
        "# ScienceBoard endpoints, merged from ScienceBoard/vm_config/server.py.\n"
        "# Restart with `sudo systemctl restart osworld.service` to take effect.",
    )
    for name in ("requests", "subprocess", "os"):
        if not re.search(rf"^(import {name}\b|from {name}\b|import .*\b{name}\b)", base, re.M):
            print(f"warning: base server does not import {name}", file=sys.stderr)
    marker = "if __name__ == '__main__':"
    i = base.index(marker)
    merged = base[:i] + block + base[i:]
    open(out_path, "w", encoding="utf-8").write(merged)
    routes = re.findall(r"@app\.route\(['\"]([^'\"]+)", merged)
    wanted = {"/opt", "/read", "/write", "/append", "/chimerax/run", "/lean/check", "/tex/check"}
    print(f"{len(routes)} routes, ScienceBoard endpoints present: {len(wanted & set(routes))}/7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
