# Migration progress and issue log

This file is updated alongside implementation work.  “Open” means the issue
has not yet passed an end-to-end test; it does not necessarily mean the design
is blocked.

## 2026-09-04

- Created an independent migration checkout at Git commit `c8d5010`.
  Development environments, logs, runtime caches, the rootfs archive, and the
  extracted VMware directory were deliberately not duplicated.
- Confirmed the source and copy had identical tracked code diffs at copy time
  (`sha256 7c4e5d6...`). The source checkout is now treated as
  read-only.
- Verified Docker Engine 29.7.2 and Compose 5.5.0 are available to the current
  non-root user.
- Inspected the live reference guest and recorded OS, desktop, application,
  dataset, filesystem, and service facts in `feasibility.md`.
- Counted 169 VM tasks across six task families and inventoried every
  initializer and verifier type.
- Exported the configured reference filesystem to the ignored artifact
  `.artifacts/scienceboard-rootfs.tar.gz` (14,100,254,851 bytes). Guest and
  host SHA-256 matched:
  `66ddd4b2f19e54e900bbf3d39782595bde2075e9e490fcb79cbe233bf586073d`.
- The first export attempt exposed two reproducibility problems: unsupported
  VMware filesystem xattrs made GNU tar return 1, and the guest clears `/tmp`
  during shutdown. The maintained exporter now omits pseudo-filesystem xattrs,
  uses `/home/user`, accepts only tar status 0/1, validates the gzip stream and
  required assets, and compares checksums before publishing the host artifact.
- Implemented the Docker lifecycle/controller adapter, immutable reset,
  Docker CLI/config validation, X11/D-Bus/AT-SPI/software-GL bootstrap,
  binary upload transport, and a Docker-specific network reset no-op.
- Added a deterministic 20-task subset covering all six applications and all
  verifier kinds.
- Ran fourteen focused unit tests successfully and completed the full static
  verifier audit: 169 tasks, 242 verifier entries, zero structural errors.
- Built the parity runtime with Xvfb, Ubuntu GNOME Shell, AT-SPI and Mesa
  llvmpipe. The runtime contract smoke test passed health, 1280x800 PNG,
  accessibility, GNOME Alt+F2, Activities application discovery,
  GL/application binaries, visible VS Code and Firefox, upload/read/write,
  recording, fresh per-container machine identity, immutable reset, and
  cleanup.
- Ran one debug initialization task for every application family:
  `6 total tested, 0 skipped`. All six reached their verifier; the six expected
  failures reflect the deliberate TIMEOUT without task actions.
- Completed the deterministic 20-task subset with the configured real key-bank
  model. The original run reported `7 passed / 12 failed / 1 skipped`; after
  making unavailable ChimeraX state fail closed and rerunning D-03, the unique
  task result is `7 passed / 13 failed / 0 skipped`.
- Re-ran Lean A-01/C-01 after the VS Code Electron wrapper: both initialized,
  accepted model actions and returned ordinary verifier failures rather than
  backend skips. The model did not produce valid proofs.
- Re-ran KAlgebra A-01 on the final GNOME runtime with the supplied key bank:
  `1 passed / 0 failed / 0 skipped`.
- Repeated that canary after sanitizing and flattening the release image; it
  again passed `1 / 1` with the supplied key bank.
- Audited the source rootfs path list and found VM shell/SSH/browser state.
  Expanded export/runtime sanitization and added an export/import flattening
  stage so deleted data is absent from the distributable image layer.
- Removed the source VM login keyring from the image baseline; each disposable
  task container starts with an empty per-container keyring instead.
- Found that Ubuntu's `/usr/bin/firefox` was only a snapd shim, which cannot
  launch on a minimal cloud container. The build now extracts the bundled
  Firefox 130 snap and installs a direct wrapper. Visible Firefox startup,
  AT-SPI discovery, and loading `example.com` pass in the runtime smoke test.
- A real TeXstudio browser task then showed that the distro Firefox desktop
  entry is deliberately hidden because snapd normally publishes its own
  replacement. The image now installs an explicit visible Activities entry;
  GNOME search and launching it are smoke-tested.
- That rerun reached Firefox but spent the remaining action budget on four
  first-run screens. A locked Firefox policy now disables onboarding,
  update/default-browser prompts, telemetry, and login saving. A clean
  container launched without a URL reaches a ready New Tab directly.
- On the final policy-enabled image, TeXstudio B-04 completed the full
  Activities -> Firefox -> Google Scholar -> Cite -> BibTeX -> TeXstudio
  clipboard path with no backend skip. The model pasted on its tenth and last
  action but did not save, so the disk-based verifier correctly returned an
  ordinary failure. This leaves the corrected 20-task score unchanged.
- A combined VS Code/Firefox accessibility probe exposed a native AT-SPI crash
  in the inherited parallel tree traversal. Linux traversal is now serial
  (PyGObject proxies are not thread-safe), skips defunct top-level roots, and
  is regression-tested with both applications open.
- The same combined probe found Electron could race for the PAM-less login
  keyring and leave a modal prompt over Firefox. The VS Code wrapper now uses
  its basic password store; the final browser smoke asserts that no keyring
  dialog is present.
- Final release image metadata: amd64, `org.scienceboard.version=0.1`,
  `org.scienceboard.distribution=sanitized-flat`, local image ID
  `sha256:6b5e0971cdff6c1248e25ea6897e5618f65bd32efe40b9a0cdc5f9ac30919ce2`,
  and content size 13,144,490,017 bytes. Sensitive-path checks and an exact
  key-bank-value repository scan passed with zero matches.
- The runner rejects intermediate images that do not carry the
  `org.scienceboard.distribution=sanitized-flat` label; this prevents an
  accidental evaluation against a non-distributable historical layer.

## 2026-09-15 distribution hardening

- Expanded the VM export and Docker overlay rules to remove Git/GnuPG identity,
  browser and editor histories, application recent sessions, Evolution and
  Nautilus metadata, PulseAudio cookies, NetworkManager keys/BSSIDs/leases,
  generated system keys, and system logs. The reusable Mathlib cache remains
  available for offline Lean verification.
- Added `scripts/audit_distribution.py`, which checks the flattening label and
  layer count, sensitive paths, non-empty state directories, image environment,
  private-key markers, and common API-token formats. The rebuilt image passes
  with zero findings.
- Repeated the full runtime smoke after hardening: X11/GNOME, screenshots,
  AT-SPI, software GL, VS Code, Firefox, upload/read/write, recording, fresh
  machine identity, immutable reset, and cleanup all pass.
- Repeated one deliberate debug initialization for every application family:
  6 tasks reached their verifier, with 0 backend skips. In three separate fresh
  containers, the exact expected TeXstudio A-04, B-04, and C-03 outputs all
  passed `/tex/check` on the first call in 0.096, 0.325, and 0.781 seconds.
- Added an audited Zstandard packaging helper and documented private review via
  Hugging Face/object storage. The one-layer image exceeds GHCR's per-layer
  limit; public distribution remains subject to third-party license review.
  The review archive is 13,092,039,138 bytes with SHA-256
  `fe4a1caf62c130f4010295b4ff5e2d761849f9c18d27bfaa2e601d7695b65c1e`.

## Issue status

| ID | Issue | State | Next evidence required |
| --- | --- | --- | --- |
| DKR-001 | Produce the immutable parity image | Passed | Required binaries/assets and image metadata checked |
| DKR-002 | Run X11/AT-SPI/GL applications without GDM | Passed | Screenshot, AT-SPI, GNOME launcher and GL probes passed |
| DKR-003 | Replace snapshot lifecycle with container reset | Passed | Mutation disappeared after container replacement |
| DKR-004 | Preserve all app helper/verifier endpoints | Passed | Six families reached verifier with zero skips |
| DKR-005 | Validate representative task coverage | Passed | Real-model deterministic 20-task run completed |
| DKR-006 | ChimeraX redistribution terms | Open/non-code | License review before publishing a prebuilt public image |

See `known-issues.md` for external-service and portability qualifications.
