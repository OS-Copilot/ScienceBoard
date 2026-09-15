# Cloud quick start (Docker only)

The evaluation host needs x86-64 Linux and Docker Engine.  It does not need
VMware, KVM, a host desktop, VNC, or a physical GPU.  The default profile uses
Mesa software rendering.

Recommended capacity for one worker is 8 vCPU, 24-32 GiB RAM, at least 80 GiB
free storage, and 2 GiB shared memory.  More CPU materially improves ChimeraX,
Celestia, TeX, and Lean startup time.

## 1. Obtain the parity image

Load an image supplied through your private artifact channel:

```bash
sha256sum -c scienceboard-docker-0.1.tar.zst.sha256
zstd -dc scienceboard-docker-0.1.tar.zst | docker load
docker image inspect --format \
  '{{.Architecture}} {{index .Config.Labels "org.scienceboard.distribution"}}' \
  scienceboard:0.1
```

Expected output is `amd64 sanitized-flat`. Maintainers can create a transport
archive with `scripts/package_distribution.sh scienceboard:0.1` and follow
[`image-delivery.md`](image-delivery.md) for private-review and public-release
constraints.

Maintainers can instead create it from the reference guest using
[`docker/export/README.md`](../docker/export/README.md).  That one-time export
is not performed on the cloud evaluation host.

## 2. Install the runner

```bash
uv venv .venv --python 3.11 --seed
uv pip install --python .venv/bin/python --torch-backend cpu -r requirements.txt
cp .env.example .env
```

Set at least these values in `.env`:

```dotenv
SCI_MODE=docker
SCI_MODEL=key_bank
SCI_TASKS_PATH=./tasks/VM
SCI_LOGS_PATH=./logs/key_bank-docker
DOCKER_IMAGE=scienceboard:0.1
KEY_BANK_PATH=/secure/path/key_bank.json
```

The key-bank secret is read at runtime and is not copied into the image or a
task container. Keep the key-bank outside this checkout if practical; `.env`,
`.artifacts`, and `logs` are excluded from both Git and Docker build context.

## 3. Validate and run

```bash
./run.sh --mode docker --check

./scripts/materialize_smoke_subset.py
./run.sh \
  --mode docker \
  --tasks .artifacts/smoke20 \
  --logs logs/docker-smoke20 \
  --no-ignore
```

Run the complete VM-compatible suite with:

```bash
./run.sh \
  --mode docker \
  --tasks tasks/VM \
  --logs logs/docker-full
```

Every task begins in a newly created container.  Containers and anonymous
volumes are force-removed on normal exit and on Python exceptions.  Evaluation
logs and recordings remain on the host under the selected logs directory.

The local acceptance run completed this exact 20-task selection against a real
key-bank model. Model outcome was 7 passed and 13 failed after the one
original verifier exception was fixed and rerun; backend/initializer skips
were zero. A final KAlgebra end-to-end canary on the release image passed 1/1.
This is infrastructure validation, not a claim that the selected model solves
all benchmark tasks.

## Security boundary

ScienceBoard intentionally executes model-generated Python and task setup
commands.  The control service listens only inside the Docker bridge when the
runner is used.  Do not publish ports 5000 or 8000 to an untrusted network.
The Compose file maps port 5000 to loopback only and is intended for manual
diagnostics.

Official task JSON is trusted host-side input because some verifier selectors
are Python lambdas.  Do not run unreviewed third-party task packs.

Only distribute the final image carrying the `sanitized-flat` label. The
rootfs and layered build images can retain removed data in lower layers. A
fresh machine ID is generated whenever a task container starts.

## Optional GPU profile

The tested baseline is CPU-only.  If a cloud host has the NVIDIA Container
Toolkit, `DOCKER_RUN_ARGS=--gpus all` can expose a GPU.  Remove or override
`LIBGL_ALWAYS_SOFTWARE=1` only after validating screenshots and the 20-task
subset, because driver-dependent rendering can change model behavior.

See [known issues](known-issues.md) before using network-dependent tasks or
publishing an image outside a private artifact channel.
