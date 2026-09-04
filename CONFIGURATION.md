# Local configuration

This checkout uses a project-local Python 3.11 environment in `.venv` and a
project-local Lean toolchain manager in `.tools`. Neither changes the system
Python, installed packages, or shell profile.

To recreate it with CPU-only PyTorch (the benchmark does not require CUDA):

```bash
uv venv .venv --python 3.11 --seed
uv pip install --python .venv/bin/python --torch-backend cpu -r requirements.txt
```

1. Copy `.env.example` to `.env` (already done in this workspace).
2. Fill the credentials and runtime paths needed by the selected mode.
3. Validate without starting an evaluation:

   ```bash
   ./run.sh --check
   ```

4. Run a single task first:

   ```bash
   ./run.sh --tasks ./tasks/Raw/Lean/A-01.json
   ```

The example configuration uses `gpt_4o` and the Raw Lean task set. It needs
`OPENAI_API_KEY`, `LEAN_LIB_PATH`, and a working `lake` command. The local
`.env` in this Docker checkout selects `key_bank` plus Docker. Docker mode needs
only Docker Engine and `DOCKER_IMAGE`; it does not read `VM_PATH` or call
`vmrun`:

```bash
./run.sh --mode docker --check
```

The tested local image is the sanitized, flattened `scienceboard:0.1` image.
Do not distribute the intermediate `scienceboard-rootfs:0.1` or
`scienceboard-layered:0.1` images: deleted source-VM files can remain in their
historical layers.

Legacy VM mode remains available and needs VMware Workstation, `vmrun`, and
`VM_PATH` pointing to `VM.zip` or a `.vmx` file:

```bash
./run.sh --mode vm --check
```

To load credentials without copying a secret into `.env`, set
`SCI_MODEL=key_bank`, `KEY_BANK_PATH`, and optionally `KEY_BANK_ENTRY` and
`KEY_BANK_MODEL`. The selected key-bank endpoint must support the
OpenAI-compatible chat-completions API. For compatibility with gateways that
silently discard system messages while routing to Claude, this model adapter
also mirrors the task prompt into each user turn.

See `docs/cloud-quickstart.md` for image loading, the deterministic 20-task
subset, full-suite commands, resource guidance, and the security boundary.

Use `./run.sh --help` for model, observation, task, logging, and resume options.
