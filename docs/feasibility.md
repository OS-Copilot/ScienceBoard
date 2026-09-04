# Docker migration feasibility

Status: **feasible for an x86-64 Linux cloud host**, with the qualifications
below.  This conclusion is based on inspection of the benchmark code and a
live inventory of the reference `sci_bench` guest, not only on package names in
the setup manual.

## What “feature parity” means

The Docker backend must preserve all benchmark-visible behavior:

- the six VM application/task families: Celestia, ChimeraX, GrassGIS,
  KAlgebra, Lean/VS Code, and TeXstudio (including the four cross-application
  TeXstudio tasks);
- a 1280x800 X11 desktop, screenshots, AT-SPI accessibility output, terminal
  output, PyAutoGUI execution, recording, setup file I/O, and application
  helper endpoints;
- isolation and reset to the same clean baseline before every task;
- the existing task JSON files, initialization hooks, prompts, agent action
  space, and verifier semantics;
- headless operation on a server with Docker but without VMware, KVM, a host X
  server, or a physical GPU.

Pixel-identical rendering is not promised across GPU drivers.  Functional UI
and verifier parity is the acceptance criterion.  The test image defaults to
Mesa/LLVMpipe so rendering does not depend on cloud GPU availability.

## Evidence from the reference image

The reference guest is Ubuntu 22.04.5 x86-64 with an Xorg/GNOME session and a
user-level Flask control service on port 5000.  Its important application
versions and assets are:

| Component | Reference value |
| --- | --- |
| Desktop | X11, 1280x800, GNOME |
| ChimeraX | 1.9 (2024-12-11) |
| GRASS GIS | 8.4.1-1~jammy1 |
| TeXstudio | 4.8.6 Ubuntu package |
| VS Code | 1.99.2 |
| Lean | 4.14.0 with Mathlib cache/project |
| Custom Qt | 6.5.0 under `/home/user/6.5.0` |
| Custom applications | `/app/bin/kalgebra`, `/app/bin/celestia-qt6` |
| GRASS data | three locations, about 676 MiB |
| Lean project/cache | about 5.5 GiB |

The guest uses about 36 GiB.  Rebuilding every historic package from current
repositories would be brittle and would change rendering and verifier
behavior.  The primary image path therefore imports the configured reference
root filesystem once and applies a small Docker overlay.  The resulting image
can be pushed to a private registry and used without VMware.

## Mapping VMware behavior to Docker

| VMware implementation | Docker implementation |
| --- | --- |
| Start a VM and discover its guest IP | Start a container and use its private bridge address |
| Revert `sci_bench` snapshot | Remove the task container and create a new one from the immutable image |
| Guest Xorg login session | Container-local Xvfb + D-Bus + Ubuntu GNOME Shell (Openbox fallback) |
| Guest service on port 5000 | Same control API inside the container |
| VMware screen recording | Same FFmpeg endpoint against display `:0` |
| VM filesystem isolation | Per-container writable layer, discarded after the task |

This reset model is stricter than a snapshot for benchmark-written files: no
state can leak from one task container to the next.

## Risks and mitigations

1. **OpenGL applications.** ChimeraX and Celestia need GLX/OpenGL.  The default
   is Mesa software rendering (`LIBGL_ALWAYS_SOFTWARE=1`).  An optional NVIDIA
   profile can be added without changing task logic.  The CPU profile will be
   slower, so readiness checks replace fixed boot assumptions where possible.
2. **Full GNOME in a container.** A GDM login is unnecessarily coupled to
   systemd and hardware seats. Xvfb plus D-Bus runs Ubuntu GNOME Shell directly
   with Mesa llvmpipe, retaining Activities, Alt+F2, the top bar, GTK/Qt themes,
   fonts, locale, and AT-SPI. Openbox remains a startup fallback.
3. **Arbitrary code execution.** The benchmark deliberately executes model
   generated Python.  The control port must only be published on loopback by
   default.  Running this service on an untrusted public network is unsafe.
4. **Image size.** The exact environment is large (the source guest uses 36
   GiB).  Multi-stage cleanup and exclusion of kernel/VM-only files reduce it,
   but a parity image is still expected to be tens of gigabytes.
5. **ChimeraX licensing.** A user may create a local/private image from the
   reference environment.  Public redistribution of a prebuilt image must be
   reviewed against the UCSF ChimeraX license; this repository will not assume
   redistribution permission.
6. **Architecture.** The supplied binaries are x86-64.  ARM cloud machines are
   out of scope unless all custom applications are rebuilt and revalidated.
7. **Source image data.** Deleting a file in a Docker overlay does not erase it
   from an older layer. The maintained import path therefore sanitizes and
   then flattens the filesystem; only the image labeled `sanitized-flat` is a
   distribution candidate.

## Decision

Proceed with a Docker-native runtime and an immutable parity image.  A cloud
user will only need Docker at evaluation time.  VMware is allowed solely as a
one-time local source-image export path while developing this migration; it is
not part of the resulting runner or cloud deployment.
