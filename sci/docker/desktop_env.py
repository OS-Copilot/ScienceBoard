"""Small Docker replacement for the subset of DesktopEnv used by ScienceBoard."""

from __future__ import annotations

import logging
import os
import subprocess
import time
import uuid
from typing import Optional, Sequence

import requests

from .controller import DockerController

LOGGER = logging.getLogger("scienceboard.docker")


class DockerRuntimeError(RuntimeError):
    """Raised when a desktop container cannot reach a usable state."""


class DockerDesktopEnv:
    """Expose the lifecycle/controller attributes expected by ``VManager``.

    A fresh container is equivalent to the old ``sci_bench`` snapshot.  The
    class intentionally does not mount the guest home directory, so removing a
    container also removes every mutation made by an agent or initializer.
    """

    server_port = 5000

    def __init__(
        self,
        image: str,
        snapshot_name: str = "sci_bench",
        docker_binary: str = "docker",
        startup_timeout: int = 240,
        run_args: Optional[Sequence[str]] = None,
    ) -> None:
        if not image:
            raise ValueError("a Docker image is required")
        if startup_timeout <= 0:
            raise ValueError("startup_timeout must be positive")

        self.image = image
        self.path_to_vm = image  # Compatibility with DesktopEnv naming.
        self.snapshot_name = snapshot_name
        self.docker_binary = docker_binary
        self.startup_timeout = startup_timeout
        self.run_args = list(run_args or ())
        self.container_name = (
            f"scienceboard-{os.getpid()}-{uuid.uuid4().hex[:10]}"
        )
        self.container_id: Optional[str] = None
        self.vm_ip: Optional[str] = None
        self.controller: Optional[DockerController] = None
        self._http = requests.Session()
        self._http.trust_env = False

        self._check_image()
        self._start_emulator()

    def _docker(
        self,
        *args: str,
        check: bool = True,
        timeout: Optional[int] = 120,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [self.docker_binary, *args],
                check=check,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = ""
            if isinstance(exc, subprocess.CalledProcessError):
                detail = (exc.stderr or exc.stdout or "").strip()
            raise DockerRuntimeError(
                f"Docker command failed: {self.docker_binary} {' '.join(args)}"
                + (f": {detail}" if detail else "")
            ) from exc

    def _check_image(self) -> None:
        self._docker("image", "inspect", self.image)

    def _container_running(self) -> bool:
        if self.container_id is None:
            return False
        result = self._docker(
            "inspect",
            "--format",
            "{{.State.Running}}",
            self.container_name,
            check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def _container_ip(self) -> str:
        result = self._docker(
            "inspect",
            "--format",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            self.container_name,
        )
        address = result.stdout.strip()
        if not address:
            raise DockerRuntimeError("desktop container has no bridge address")
        return address

    def _diagnostics(self) -> str:
        if self.container_id is None:
            return "container was not created"
        state = self._docker(
            "inspect", "--format", "{{json .State}}", self.container_name,
            check=False,
        )
        logs = self._docker(
            "logs", "--tail", "120", self.container_name, check=False,
        )
        return (
            f"state={state.stdout.strip() or state.stderr.strip()}\n"
            f"logs:\n{logs.stdout}{logs.stderr}"
        ).strip()

    def _start_emulator(self) -> None:
        if self._container_running():
            return

        # A failed previous launch may have left a stopped name behind.
        self._remove_container(ignore_missing=True)
        command = [
            "run",
            "--detach",
            "--pull", "never",
            "--init",
            "--name", self.container_name,
            "--hostname", "scienceboard",
            "--shm-size", "2g",
            "--label", "org.scienceboard.runtime=true",
            "--env", "DISPLAY=:0",
            "--env", "LIBGL_ALWAYS_SOFTWARE=1",
            "--env", "GALLIUM_DRIVER=llvmpipe",
            *self.run_args,
            self.image,
        ]
        result = self._docker(*command, timeout=self.startup_timeout)
        self.container_id = result.stdout.strip()

        deadline = time.monotonic() + self.startup_timeout
        last_error = "control service has not responded"
        while time.monotonic() < deadline:
            if not self._container_running():
                break
            try:
                self.vm_ip = self._container_ip()
                response = self._http.get(
                    f"http://{self.vm_ip}:{self.server_port}/health",
                    timeout=2,
                )
                if response.status_code == 200:
                    # A healthy API is not enough: wait until X can render.
                    shot = self._http.get(
                        f"http://{self.vm_ip}:{self.server_port}/screenshot",
                        timeout=10,
                    )
                    if shot.status_code == 200 and shot.content.startswith(b"\x89PNG"):
                        # The third-party controller uses the module-level
                        # requests helpers.  Ensure bridge traffic never leaks
                        # into a cloud host's outbound HTTP proxy.
                        for variable in ("NO_PROXY", "no_proxy"):
                            current = os.environ.get(variable, "")
                            entries = [item for item in current.split(",") if item]
                            if self.vm_ip not in entries:
                                entries.append(self.vm_ip)
                            os.environ[variable] = ",".join(entries)
                        self.controller = DockerController(
                            vm_ip=self.vm_ip,
                            server_port=self.server_port,
                        )
                        return
                last_error = f"HTTP {response.status_code} from /health"
            except (requests.RequestException, DockerRuntimeError) as exc:
                last_error = str(exc)
            time.sleep(1)

        diagnostics = self._diagnostics()
        self._remove_container(ignore_missing=True)
        raise DockerRuntimeError(
            f"desktop container did not become ready within "
            f"{self.startup_timeout}s ({last_error})\n{diagnostics}"
        )

    def _remove_container(self, ignore_missing: bool = False) -> None:
        result = self._docker(
            "rm", "--force", "--volumes", self.container_name,
            check=False,
            timeout=60,
        )
        if result.returncode != 0 and not ignore_missing:
            message = (result.stderr or result.stdout).strip()
            raise DockerRuntimeError(
                f"could not remove container {self.container_name}: {message}"
            )
        self.container_id = None
        self.vm_ip = None
        self.controller = None

    def _revert_to_snapshot(self) -> str:
        if self.snapshot_name != "sci_bench":
            raise DockerRuntimeError(
                f"Docker image has no baseline named {self.snapshot_name!r}"
            )
        self._remove_container(ignore_missing=True)
        return self.image

    def close(self) -> None:
        self._remove_container(ignore_missing=True)
