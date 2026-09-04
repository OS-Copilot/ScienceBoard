#!/usr/bin/env python3
"""Create a Docker-importable rootfs archive from the reference VM.

This is a maintainer migration tool.  Images produced from it run without
VMware; cloud users should consume the resulting private image/archive.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests


REMOTE_ARCHIVE = "/home/user/scienceboard-rootfs.tar.gz"
REMOTE_DONE = "/home/user/scienceboard-rootfs.done"
REMOTE_FAILED = "/home/user/scienceboard-rootfs.failed"

EXPORT_SCRIPT = r"""#!/usr/bin/env bash
set -u
archive=/home/user/scienceboard-rootfs.tar.gz
rm -f "$archive" /home/user/scienceboard-rootfs.done /home/user/scienceboard-rootfs.failed
set +e
tar --numeric-owner --one-file-system --warning=no-file-changed --ignore-failed-read \
  --exclude='./proc' --exclude='./sys' --exclude='./dev' --exclude='./run' \
  --exclude='./tmp' --exclude='./mnt' --exclude='./media' \
  --exclude='./lost+found' --exclude='./swapfile' --exclude='./var/log/*' \
  --exclude='./home/user/server/screenshots/*' \
  --exclude='./home/user/scienceboard-rootfs*' \
  --exclude='./etc/ssh/ssh_host_*' \
  --exclude='./root/.ssh' --exclude='./home/user/.ssh' \
  --exclude='./root/.bash_history' --exclude='./root/.python_history' \
  --exclude='./home/user/.bash_history' --exclude='./home/user/.python_history' \
  --exclude='*/.bash_history' --exclude='*/.python_history' \
  --exclude='*/cookies.sqlite*' --exclude='*/logins.json' \
  --exclude='*/key4.db' --exclude='*/formhistory.sqlite' \
  --exclude='*/places.sqlite*' --exclude='*/sessionstore-backups' \
  --exclude='./home/user/.config/Code/Cookies*' \
  --exclude='./home/user/.config/Code/Network Persistent State' \
  --exclude='./home/user/.local/share/keyrings' \
  --exclude='./var/lib/systemd/random-seed' \
  --exclude='./etc/NetworkManager/system-connections/*' \
  --exclude='./etc/machine-id' --exclude='./var/lib/dbus/machine-id' \
  -C / -cpf - . | gzip -1 > "$archive"
pipe_status=("${PIPESTATUS[@]}")
set -e
if [[ ${pipe_status[1]} -eq 0 && ${pipe_status[0]} -le 1 ]] \
  && gzip -t "$archive" \
  && tar -tzf "$archive" \
       ./app/bin/kalgebra \
       ./app/bin/celestia-qt6 \
       ./usr/bin/chimerax \
       ./home/user/sci/Sci/Basic.lean \
       ./home/user/grassdata \
       >/home/user/scienceboard-rootfs.key-files; then
  sha256sum "$archive" > /home/user/scienceboard-rootfs.done
else
  printf 'tar=%s gzip=%s\n' "${pipe_status[0]}" "${pipe_status[1]}" \
    > /home/user/scienceboard-rootfs.failed
fi
"""


def vmrun(*args: str, timeout: int = 180) -> str:
    result = subprocess.run(
        ["vmrun", "-T", "ws", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def execute(session: requests.Session, ip: str, command: list[str]) -> dict:
    response = session.post(
        f"http://{ip}:5000/execute",
        json={"command": command, "shell": False},
        timeout=300,
    )
    response.raise_for_status()
    result = response.json()
    if result.get("returncode") != 0:
        raise RuntimeError(result.get("error") or result)
    return result


def wait_for_guest(session: requests.Session, vmx: Path, timeout: int) -> str:
    deadline = time.monotonic() + timeout
    last_error = "no IP"
    while time.monotonic() < deadline:
        try:
            ip = vmrun("getGuestIPAddress", str(vmx), "-wait", timeout=30)
            response = session.get(f"http://{ip}:5000/platform", timeout=2)
            if response.ok:
                return ip
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:  # readiness retries need the final diagnostic
            last_error = str(exc)
        time.sleep(2)
    raise TimeoutError(f"reference guest did not become ready: {last_error}")


def remote_state(session: requests.Session, ip: str) -> str:
    command = [
        "bash", "-lc",
        f"if test -f {REMOTE_DONE}; then echo DONE; "
        f"elif test -f {REMOTE_FAILED}; then echo FAILED; "
        f"elif test -f {REMOTE_ARCHIVE}; then stat -c 'RUNNING %s' {REMOTE_ARCHIVE}; "
        "else echo STARTING; fi",
    ]
    return execute(session, ip, command).get("output", "").strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("vmx", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".artifacts/scienceboard-rootfs.tar.gz"),
    )
    parser.add_argument("--snapshot", default="sci_bench")
    parser.add_argument("--guest-password", default="password")
    parser.add_argument("--startup-timeout", type=int, default=180)
    parser.add_argument("--export-timeout", type=int, default=3600)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if shutil.which("vmrun") is None:
        parser.error("vmrun is required only for this one-time maintainer export")
    vmx = args.vmx.resolve()
    if not vmx.is_file():
        parser.error(f"VMX does not exist: {vmx}")
    output = args.output.resolve()
    if output.exists() and not args.force:
        parser.error(f"output already exists (use --force): {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".part")

    session = requests.Session()
    session.trust_env = False
    started = False
    try:
        vmrun("revertToSnapshot", str(vmx), args.snapshot)
        vmrun("start", str(vmx), "nogui")
        started = True
        ip = wait_for_guest(session, vmx, args.startup_timeout)

        payload = base64.b64encode(EXPORT_SCRIPT.encode()).decode()
        execute(session, ip, [
            "bash", "-lc",
            f"printf %s {shlex.quote(payload)} | base64 -d "
            "> /home/user/scienceboard-export.sh "
            "&& chmod 700 /home/user/scienceboard-export.sh",
        ])
        execute(session, ip, [
            "bash", "-lc",
            f"printf '%s\\n' {shlex.quote(args.guest_password)} | sudo -S "
            "bash -c 'nohup /home/user/scienceboard-export.sh "
            ">/home/user/scienceboard-rootfs.export.log 2>&1 &'",
        ])

        deadline = time.monotonic() + args.export_timeout
        while time.monotonic() < deadline:
            state = remote_state(session, ip)
            print(state, flush=True)
            if state == "DONE":
                break
            if state == "FAILED":
                detail = execute(session, ip, [
                    "bash", "-lc",
                    f"cat {REMOTE_FAILED} /home/user/scienceboard-rootfs.export.log",
                ]).get("output", "")
                raise RuntimeError(f"rootfs export failed:\n{detail}")
            time.sleep(15)
        else:
            raise TimeoutError("rootfs export timed out")

        expected = execute(
            session, ip, ["cat", REMOTE_DONE]
        )["output"].split()[0]
        digest = hashlib.sha256()
        with session.post(
            f"http://{ip}:5000/file",
            data={"file_path": REMOTE_ARCHIVE},
            stream=True,
            timeout=(10, 3600),
        ) as response:
            response.raise_for_status()
            with partial.open("wb") as writable:
                for chunk in response.iter_content(8 * 1024 * 1024):
                    if chunk:
                        writable.write(chunk)
                        digest.update(chunk)
        actual = digest.hexdigest()
        if actual != expected:
            raise RuntimeError(f"checksum mismatch: guest={expected}, host={actual}")
        os.replace(partial, output)
        print(f"archive={output}")
        print(f"bytes={output.stat().st_size}")
        print(f"sha256={actual}")
        return 0
    finally:
        if partial.exists():
            partial.unlink()
        if started:
            subprocess.run(
                ["vmrun", "-T", "ws", "stop", str(vmx), "soft"],
                capture_output=True,
                timeout=180,
            )


if __name__ == "__main__":
    raise SystemExit(main())
