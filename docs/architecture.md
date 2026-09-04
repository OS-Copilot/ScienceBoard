# Docker backend architecture

## Lifecycle

Each application-family manager owns one Docker container at a time:

1. `VManager.__enter__` constructs `DockerDesktopEnv`, which validates Docker
   and the configured image.
2. The backend creates a fresh container and waits for both `/health` and a
   valid PNG from `/screenshot`.
3. Before each task, `revert("sci_bench")` removes that container and creates a
   fresh one from the same immutable image.
4. Existing task initialization runs through the unchanged HTTP endpoints.
5. Observations, model actions, recordings, and verifiers use a controller
   with the same methods as `desktop_env`'s Python controller.
6. `VManager.__exit__` force-removes the container and anonymous volumes even
   after an exception.

The runner reaches the control service through the container's private bridge
address; it publishes no host port. Proxy variables are bypassed for that
address. The diagnostic Compose profile publishes port 5000 on loopback only.

## Repository components

- `sci/docker/desktop_env.py`: Docker Engine CLI lifecycle and immutable reset.
- `sci/docker/controller.py`: HTTP control client compatible with `VManager`.
- `docker/Dockerfile`: runtime and sanitizing overlay applied to the parity
  root filesystem.
- `docker/entrypoint.sh` and `docker/session.sh`: Xvfb, system/session D-Bus,
  Ubuntu GNOME Shell, AT-SPI, and API startup; Openbox is a startup fallback.
- `docker/flatten_image.sh` and `docker/Portable.Dockerfile`: collapse the
  sanitized filesystem and restore metadata for private distribution.
- `docker/export/`: reproducible one-time tooling that creates a Docker import
  archive from the reference guest without putting the archive in Git.
- `docker-compose.yml`: manual debugging and cloud smoke-test entry point.
- `scripts/materialize_smoke_subset.py`: deterministic 20-task coverage subset.
- `scripts/smoke_docker_runtime.py`: desktop/API/reset contract test.

The GNOME session preserves benchmark-relevant global behavior such as the
Activities overview, top bar, maximization, and Alt+F2 command launcher.
Electron is started through a narrowly scoped VS Code wrapper with
`--no-sandbox --disable-gpu`. The bundled Firefox snap is extracted at build
time and launched directly because cloud containers do not run snapd. A
visible desktop entry preserves Activities discovery and an enterprise policy
suppresses first-run onboarding. The GNOME keyring is explicitly unlocked
because there is no GDM/PAM login. Native GL applications use Mesa llvmpipe.

## Compatibility boundary

Task definitions and application-specific managers do not know which desktop
provider is active. `main.py` selects `vm` or `docker`, and the tester builds
the corresponding manager. The Docker implementation preserves this manager
surface:

`revert`, `screenshot`, `a11y_tree`, `textual`, `set_of_marks`, `read_file`,
`write_file`, `append_file`, `upload_file`, `record_start`, `record_stop`,
`_request`, and PyAutoGUI execution through `__call__`.

Task grouping compares the complete `sort.type` identity. This prevents two
different VM application families with otherwise equal provider settings from
sharing and deleting one another's lifecycle registry entry.
