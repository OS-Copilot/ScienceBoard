#!/usr/bin/env python3
"""Fail if a distributable ScienceBoard image retains common private state."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import textwrap


IMAGE_AUDIT = r'''
from __future__ import annotations

import json
import re
from pathlib import Path


forbidden_paths = (
    "/etc/brlapi.key",
    "/etc/ssl/private/ssl-cert-snakeoil.key",
    "/etc/ssl/certs/ssl-cert-snakeoil.pem",
    "/root/.gitconfig",
    "/root/.gnupg",
    "/root/.aws",
    "/root/.azure",
    "/root/.docker",
    "/root/.huggingface",
    "/root/.kube",
    "/root/.config/gh",
    "/root/.config/gcloud",
    "/root/.local/share/recently-used.xbel",
    "/home/user/.gitconfig",
    "/home/user/.gnupg",
    "/home/user/.aws",
    "/home/user/.azure",
    "/home/user/.docker",
    "/home/user/.huggingface",
    "/home/user/.kube",
    "/home/user/.config/gh",
    "/home/user/.config/gcloud",
    "/home/user/.mozilla",
    "/home/user/snap/firefox",
    "/home/user/.config/Code/User/globalStorage",
    "/home/user/.config/Code/User/workspaceStorage",
    "/home/user/.config/Code/User/History",
    "/home/user/.config/Code/Backups",
    "/home/user/.config/texstudio/cache",
    "/home/user/.config/texstudio/lastSession.txss2",
    "/home/user/.config/goa-1.0",
    "/home/user/.config/pulse",
    "/home/user/.config/evolution",
    "/home/user/.dotnet",
    "/home/user/.pki",
    "/home/user/.local/share/recently-used.xbel",
    "/home/user/.local/share/Celestia/bookmarks.xbel",
    "/home/user/.local/share/evolution",
    "/home/user/.local/share/gvfs-metadata",
    "/home/user/.local/share/nautilus/tags",
    "/home/user/.local/share/xorg",
    "/var/lib/AccountsService/users/user",
)
empty_directories = (
    "/root/.ssh",
    "/home/user/.ssh",
    "/home/user/.local/share/keyrings",
    "/var/lib/NetworkManager",
)
private_file_globs = (
    "/home/user/.miktex/texmfs/data/miktex/log/*.log",
    "/var/log/**/*",
)
credential_names = {
    ".env", ".netrc", ".git-credentials", ".npmrc", ".pypirc",
    "authorized_keys", "id_rsa", "id_ed25519", "logins.json", "key4.db",
}
token_patterns = {
    "OpenAI-style key": re.compile(rb"sk-[A-Za-z0-9_-]{24,}"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "Google API key": re.compile(rb"AIza[A-Za-z0-9_-]{20,}"),
    "AWS access key": re.compile(rb"AKIA[A-Z0-9]{16}"),
    "Hugging Face token": re.compile(rb"hf_[A-Za-z0-9]{24,}"),
    "private key": re.compile(rb"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
}

findings = []
for name in forbidden_paths:
    if Path(name).exists():
        findings.append({"kind": "forbidden_path", "path": name})
for name in empty_directories:
    path = Path(name)
    if path.exists() and any(path.iterdir()):
        findings.append({"kind": "nonempty_private_directory", "path": name})
for pattern in private_file_globs:
    for path in Path("/").glob(pattern.lstrip("/")):
        if path.is_file() and path.stat().st_size:
            findings.append({"kind": "nonempty_log", "path": str(path)})

machine_id = Path("/etc/machine-id")
if not machine_id.is_file() or machine_id.stat().st_size != 0:
    findings.append({"kind": "persistent_machine_id", "path": str(machine_id)})

scan_roots = (Path("/root"), Path("/home/user"), Path("/etc"))
token_scan_excludes = (
    Path("/home/user/.local/lib"),
)
for root in scan_roots:
    for path in root.rglob("*"):
        try:
            if not path.is_file():
                continue
            if path.name in credential_names:
                findings.append({"kind": "credential_file", "path": str(path)})
                continue
            size = path.stat().st_size
            if size == 0 or size > 5_000_000:
                continue
            if any(excluded == path or excluded in path.parents
                   for excluded in token_scan_excludes):
                # Vendored Python packages contain example identifiers that
                # resemble credentials. Their source is reproducible from the
                # package environment and is not VM user state.
                continue
            data = path.read_bytes()
        except (OSError, PermissionError):
            continue
        if b"\0" in data[:8192]:
            continue
        for label, pattern in token_patterns.items():
            if pattern.search(data):
                findings.append({"kind": label, "path": str(path)})

print(json.dumps({"findings": findings}, sort_keys=True))
raise SystemExit(1 if findings else 0)
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="scienceboard:0.1")
    args = parser.parse_args()

    inspected = subprocess.run(
        ["docker", "image", "inspect", args.image],
        capture_output=True,
        text=True,
    )
    if inspected.returncode != 0:
        parser.error(f"Docker image does not exist: {args.image}")

    metadata = json.loads(inspected.stdout)[0]
    metadata_findings = []
    labels = metadata.get("Config", {}).get("Labels") or {}
    if labels.get("org.scienceboard.distribution") != "sanitized-flat":
        metadata_findings.append({
            "kind": "unsafe_distribution_label",
            "path": "image config",
        })
    if len(metadata.get("RootFS", {}).get("Layers", [])) != 1:
        metadata_findings.append({
            "kind": "unflattened_image",
            "path": "image layers",
        })
    for item in metadata.get("Config", {}).get("Env") or []:
        name, separator, value = item.partition("=")
        if (separator and value and
                re.search(r"(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)",
                          name, re.IGNORECASE)):
            metadata_findings.append({
                "kind": "credential_environment_variable",
                "path": name,
            })

    result = subprocess.run(
        [
            "docker", "run", "--rm", "--entrypoint", "/usr/bin/python3",
            args.image, "-c", textwrap.dedent(IMAGE_AUDIT),
        ],
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        print(result.stderr or result.stdout, file=sys.stderr)
        return 2

    findings = metadata_findings + report.get("findings", [])
    print(json.dumps({
        "image": args.image,
        "passed": not findings,
        "finding_count": len(findings),
        "findings": findings,
    }, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
