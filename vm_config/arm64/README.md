# ARM64 unified VM (VMware Fusion on Apple Silicon)

Build materials for a single arm64 Ubuntu 22.04 VM that carries the OSWorld 1.0
applications plus the ScienceBoard application families. The base is OSWorld's
`Ubuntu-arm.zip` (HF `xlangai/ubuntu_osworld`), so OSWorld tasks and
ScienceBoard tasks share one image. Comparability with the published x86
numbers is not a goal of this image.

## Host state (Mac Studio, 2026-10-13)

- VM: `~/Virtual Machines.localized/OSWorld-arm.vmwarevm/Ubuntu.vmx`,
  10 vCPU, 24 GB, 200 GB thin disk, 1920x1080, NAT, user `user` / `password`.
- Snapshots are powered-off snapshots. Lazy running-state snapshots stall on
  Fusion 26 (a few MB/s), so each reset boots the guest: revert + boot to the
  control server took 51 s.
- `init_state`: OSWorld base layer (OSWorld quickstart passes).
- `sci_layer_lean`, `sci_layer_tex`: intermediate checkpoints.
- `sci_bench`: OSWorld base + Lean + TeX + GRASS + Celestia + KAlgebra. This is the
  snapshot ScienceBoard's `VManager` reverts to; point OSWorld's `DesktopEnv`
  at it (`snapshot_name="sci_bench"`) to run OSWorld tasks on the unified image.

## Guest control server

`server.py` is the VM's OSWorld server (`/home/user/server/main.py`, systemd
unit `osworld.service`, same routes as `xlang-ai/osworld-server`) with the
seven ScienceBoard endpoints appended: `/opt`, `/read`, `/write`, `/append`,
`/chimerax/run`, `/lean/check`, `/tex/check`. The original is kept in the
guest as `/home/user/server/main.py.osworld-orig`. The serial AT-SPI traversal
from `vm_config/server.py` was not ported; the shared server still traverses in
parallel.

## Guest prerequisites applied once

- apt sources: the OSWorld ARM image shipped `/etc/apt/sources.list` pointing
  at `us.archive.ubuntu.com` (amd64/i386 only) plus `jammy-proposed`. Replaced
  with `guest/sources.list.arm64` (ports.ubuntu.com/ubuntu-ports); the original
  is kept as `/etc/apt/sources.list.archive-orig`. The image was built with
  `jammy-proposed` enabled (for example libicu70 70.1-2ubuntu1 is installed and
  only exists there), so `sources.list.d/proposed.list` now points at
  `ports.ubuntu.com/ubuntu-ports jammy-proposed`; without it `-dev` packages
  such as libicu-dev cannot match the installed runtime libraries.
- apt periodic updates and the update notifier are disabled
  (`guest/quiet-updates.sh`) so no "Software Updates Available" popup appears
  during tasks.

## Application layers

| Layer | Script | Status |
| --- | --- | --- |
| Lean 4.14.0 + Mathlib v4.14.0 project at `/home/user/sci`, VS Code `leanprover.lean4` | `guest/lean-setup.sh` | done, snapshot `sci_layer_lean` |
| TeXstudio 4.8.6 (PPA sunderme) + texlive-full (TeX Live 2021) | `guest/tex-setup.sh` | done, snapshot `sci_layer_tex` |
| GRASS GIS 8.4.2 built from source into /usr/local/grass84 (the ubuntugis-unstable PPA ships grass-core/grass-gui 8.4.2 for amd64 only) + ShiinaHiiragi/grass-gui + sample locations from grass.osgeo.org / Zenodo | `guest/grass-setup.sh` (data, PPA attempt), `guest/grass-source-build.sh`, then `guest/wxpython-build.sh` (GRASS 8.4's GUI needs wxPython >= 4.2; Ubuntu 22.04 arm64 only has 4.0.7 and the PPA's 4.2.1 is amd64-only, so it is built from the PyPI sdist with setuptools 70.3.0 + wheel 0.45.1 pinned in the user site) | done; GUI opens the location and `/dump` on :8000 answers |
| Celestia fork, native Qt 6.2.4 build into /app (`/app/bin/celestia-qt6`) + CelestiaContent | `guest/celestia-build.sh` | done; state server on :8000 answers `/dump` |
| KAlgebra fork as Flatpak `org.kde.kalgebra` (org.kde.Platform/Sdk 6.7 + io.qt.qtwebengine.BaseApp 6.7; the script patches the fork at build time: skips the deb-only patchelf bundling, adds `<cstdint>` to the HTTP server, exposes `PlotsModel::m_items/m_resolution` in the installed Analitza header, installs the desktop file) with `/app/bin/kalgebra` wrapping `flatpak run --share=network` | `guest/kalgebra-flatpak.sh` | done; `/version` and `/vars` on :8000 answer |
| ChimeraX (no arm64 build; source build) | | deferred |
| OSWorld-V2 app delta, arm64 subset (Obsidian, MuseScore, REAPER, apt Audacity/Blender/Shotcut/LabPlot, Node.js, Chrome policy, Xorg MaxClients, MIME defaults) | `guest/v2-delta-arm64.sh` | planned |

GRASS data differs from the reference VM: the sample datasets are downloaded
from grass.osgeo.org and the two hand-placed points used by D-04 are not
reproduced.

## Runner-side changes

- `sci/vm/vmanager.py`: `vmrun -T fusion` on macOS.
- `.env`: `VM_PATH` should point at the vmx above; `__VERSION__` = `0.1` next
  to the vmx is required by `VManager`.

## OSWorld-V2 notes

- V2's "task service ports" 3000/8000 belong to the self-hosted mocked websites
  (`Task-Web/OSWorld-web`, `/api/state`), not to the client image.
- V2 pins `osworld-server` at a3cc3f0 (2026-05-18), which moved the Flask
  routes to `src/http_routes.py` and adds FastAPI/uvicorn streaming. The guest
  still runs the 2025-08 single-file server; `merge_scienceboard_endpoints.py`
  needs a different insertion point before that upgrade.
- V2 task classes and assets are gated Hugging Face datasets; the V2 host
  environment is `~/Git-Repos/OSWorld-V2/.venv` (Python 3.12, `uv sync --frozen`).
- No arm64 builds: XMind, Zotero 8.0.2, official Blender/Shotcut/LabPlot
  AppImages (apt versions are older). WPS arm64 package URL not verified.

## Smoke test (2026-10-13)

`run_debug_smoke.sh` ran one VM task per family in debug/TIMEOUT mode against
`sci_bench`: Lean A-01, TeXstudio B-01, GrassGIS A-01, Celestia A-01,
KAlgebra A-01. All five initialized (snapshot revert, boot, app launch, task
setup) and reached evaluation with 0 skipped; each failed with TIMEOUT as
designed because no actions were taken. Wall time was 615 s for the five tasks,
about 2 min per task including the 55 s boot.

## Not done

- ChimeraX (29 VM tasks, 4 TeXstudio cross-app tasks, 29 Dual tasks): no Linux
  arm64 build; needs a source build or a different route.
- OSWorld-V2 delta (`guest/v2-delta-arm64.sh` is drafted, not run) and the
  osworld-server upgrade to the V2 pin.
- The two hand-placed GRASS points of task D-04.

## Real-model runs (2026-10-13, gpt-4o-2024-08-06 through the key-bank gateway)

- Raw Lean A-01: passed in 80 s (5 tactic steps, DONE).
- VM Lean A-01, Celestia A-01, KAlgebra A-01: all initialized, the model
  produced pyautogui actions (15 to 65 code blocks per task), evaluation ran,
  all three failed (two TIMEOUT, KAlgebra DONE but wrong). 49 min for the three.
  This is a pipeline check, not a benchmark number.

## ChimeraX on the host (Raw mode)

ChimeraX has no Linux arm64 build, so ChimeraX tasks run natively on macOS:
ChimeraX 1.9 (arm64) is installed in `/Applications/ChimeraX-1.9.app` with
`chimerax` and `chimerax-daily` symlinks in `/opt/homebrew/bin` (the Raw
manager's "daily" sort runs `chimerax-daily`). The 29 VM ChimeraX tasks were
converted to Raw tasks in `.artifacts/tasks-raw-chimerax/` (sort Raw, version
0.5, VM-only `execute`/`launch` steps dropped, guest asset paths rewritten to
`.artifacts/chimerax-assets/`, which holds `vm_config/pack`'s ChimeraX files).
The four TeXstudio+ChimeraX cross-app tasks and the Dual set still need
ChimeraX inside the VM.

Unattended Raw run of A-01 (debug/TIMEOUT): ChimeraX launched, the
chimerax-states bundle installed, the task initialized (open 2olx, turn) and the
state-based evaluation ran, 55 s, 0 skipped. `sci/ChimeraX/chimerax.py` had its
REST startup timeout raised from 15 s to 120 s because GUI ChimeraX on this Mac
needs more than 15 s before it prints the REST line (uncommitted). A real-model
run additionally needs macOS Screen Recording and Accessibility permissions for
the terminal that runs ScienceBoard, and a leftover ChimeraX holding port 8000
makes the manager block in `readline()`; kill stray `chimerax-daily` processes
before a run.

## OSWorld-V2 on the unified VM (2026-10-13)

Task classes (108) and the asset snapshot (4.6 GB) for osworld-v2.1 are in
`~/Git-Repos/OSWorld-V2` (`evaluation_examples/task_class`,
`cache/osworld_v2_assets_v2.1`). 7 tasks depend on the mocked websites and 2 on
GitLab; 66 need only OSWorld-base applications; the rest need the V2 app delta
(WPS 13, Shotcut 6, Zotero 5, REAPER 3, LabPlot 2, MuseScore 2, Obsidian 2,
Blender 1).

`v2_vmware_smoke.py` ran tasks 001, 002, 003 on `sci_bench` (VMware provider,
client password `password`, `OSWORLD_FILE_BASE_URL` set): all three completed
setup and evaluation with score 0 and no exception (415 s). Task 002's setup
launches a task-local web app (`/tmp/Class-Planner/run.py`) that timed out
after 120 s, so the V2 delta's Node.js/Python runtime pieces are still needed
for such tasks.
