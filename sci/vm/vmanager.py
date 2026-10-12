import sys
import os
import re
import json
import zipfile
import subprocess

from io import BytesIO
from typing import Optional, Union, Iterable, Tuple, Dict, Any, List
from typing import Self, NoReturn, Callable, TypedDict, NotRequired

import requests
from PIL import Image

sys.dont_write_bytecode = True
from ..base import Manager
from ..base import GLOBAL_VLOG
from ..base.utils import error_factory

from .. import Prompts
from . import utils

ENVS = {}

class VirtualEnv(TypedDict):
    provider_name: NotRequired[str]
    region: NotRequired[str]
    path_to_vm: NotRequired[str]
    snapshot_name: NotRequired[str]
    action_space: NotRequired[str]
    cache_dir: NotRequired[str]
    screen_size: NotRequired[Tuple[int]]
    headless: NotRequired[bool]
    require_a11y_tree: NotRequired[bool]
    require_terminal: NotRequired[bool]
    os_type: NotRequired[str]
    docker_binary: NotRequired[str]
    docker_startup_timeout: NotRequired[int]
    docker_run_args: NotRequired[List[str]]


class VManager(Manager):
    ISO_PATH = "/tmp/ubuntu.iso"
    VM_PATH = "vmware"
    VMX_NAME = "Ubuntu.vmx"
    VERSION_NAME = "__VERSION__"

    INIT_NAME = "sci_bench"
    SERVER_PORT = 5000

    def __init__(
        self,
        version: str = "0.1",
        vm_path: Optional[str] = None,
        headless: bool = False,
        a11y_tree_limit: int = 10240,
        provider_name: str = "vmware",
        docker_image: Optional[str] = None,
        docker_binary: str = "docker",
        docker_startup_timeout: int = 240,
        docker_run_args: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        super().__init__(version)

        assert provider_name in {"vmware", "docker"}
        self.provider_name = provider_name
        if self.provider_name == "vmware":
            assert vm_path is not None
            self.__vm_path(vm_path)
        else:
            self.path = (docker_image or vm_path or "").strip()
            if not self.path:
                raise ValueError("docker_image is required for the Docker backend")

        assert isinstance(headless, bool)
        self.headless = headless

        self.env = VirtualEnv(
            provider_name=self.provider_name,
            region=None,
            path_to_vm=self.path,
            snapshot_name=VManager.INIT_NAME,
            action_space="pyautogui",
            headless=self.headless,
            docker_binary=docker_binary,
            docker_startup_timeout=docker_startup_timeout,
            docker_run_args=list(docker_run_args or []),
        )

        assert isinstance(a11y_tree_limit, int)
        self.a11y_tree_limit = a11y_tree_limit

        # if not os.path.exists(VManager.ISO_PATH):
        #     open(VManager.ISO_PATH, mode="w").close()

    @property
    def env(self):
        global ENVS
        return ENVS[self.key] if hasattr(self, "key") else None

    @env.setter
    def env(self, value: VirtualEnv) -> None:
        # TypedDict does not support instance and class checks
        assert isinstance(value, dict)
        # Managers for different application families can have identical
        # provider settings.  They still need independent lifecycle entries;
        # otherwise leaving the first task group deletes the shared registry
        # entry and the next group cannot enter its manager.
        self.key = f"{json.dumps(value, sort_keys=True)}:{id(self)}"

        global ENVS
        if value["provider_name"] == "docker":
            def env_factory():
                from ..docker import DockerDesktopEnv

                return DockerDesktopEnv(
                    image=value["path_to_vm"],
                    snapshot_name=value["snapshot_name"],
                    docker_binary=value["docker_binary"],
                    startup_timeout=value["docker_startup_timeout"],
                    run_args=value["docker_run_args"],
                )
        else:
            def env_factory():
                # Only load desktop_env when needed, so Docker-only cloud
                # deployments do not initialize a virtualization provider.
                from desktop_env.desktop_env import DesktopEnv

                return DesktopEnv(**{
                    key: item for key, item in value.items()
                    if not key.startswith("docker_")
                })
        self._env_factory = env_factory
        ENVS[self.key] = self._env_factory

    @property
    def controller(self):
        return getattr(getattr(self, "env", None), "controller", None)

    @property
    def entered(self) -> bool:
        return (
            hasattr(self, "key")
            and self.key in ENVS
            and not hasattr(ENVS[self.key], "__call__")
        )

    @entered.setter
    def entered(self, value) -> None:
        # ignore assignment
        ...

    def __is_zip(self, file_path: str):
        assert os.path.exists(file_path)
        with open(file_path, mode="rb") as readble:
            magic_number = readble.read(4)
        return magic_number == b"PK\x03\x04"

    # - check if vm_path is Ubuntu.zip file (and extract)
    # - record vm_path to Ubuntu.vmx file
    def __vm_path(self, vm_path: str):
        if self.__is_zip(vm_path):
            cwd = os.path.join(os.path.abspath("."), VManager.VM_PATH)
            with zipfile.ZipFile(vm_path, "r") as zip_ref:
                GLOBAL_VLOG.info("Starting to extract the .zip file...")
                zip_ref.extractall(cwd)
                GLOBAL_VLOG.info("Files were extracted successfully.")
                vm_path = os.path.join(cwd, VManager.VMX_NAME)

        assert os.path.exists(vm_path)
        self.path = vm_path

        # version argument should be consistent with vm file
        # no more check required if this assertion pass
        with open(os.path.join(
            os.path.split(self.path)[0],
            VManager.VERSION_NAME
        ), mode="r", encoding="utf-8") as readble:
            assert(readble.read().strip() == self.version)

        snapshot_detect = self._list_snapshots()
        assert snapshot_detect is not None
        impure_snapshots = snapshot_detect.split("\n")
        if VManager.INIT_NAME not in impure_snapshots:
            GLOBAL_VLOG.input((
                f"Snapshot {VManager.INIT_NAME} will be created automatically; "
                f"press ENTER to continue: "
            ), end="")
            assert self._create_snapshots(VManager.INIT_NAME) is True

    @staticmethod
    def _env_handler(method: Callable) -> Callable:
        def _env_wrapper(self: "VManager", *args, **kwargs) -> Any:
            assert self.entered
            return method(self, *args, **kwargs)
        return _env_wrapper

    # hard to use, try OSWorld's service instead
    def _vmrun(
        self,
        command: str,
        *args: str,
        tolerance: Iterable[int] = []
    ) -> Tuple[str, bool]:
        assert self.provider_name == "vmware"
        assert isinstance(command, str)
        for arg in args:
            assert isinstance(arg, str)

        assert isinstance(tolerance, Iterable)
        for return_code in tolerance:
            assert isinstance(return_code, int)
        tolerance = set(tolerance)
        tolerance.add(0)

        completed = subprocess.run([
            "vmrun",
            "-T",
            "ws",
            "-gu",
            Prompts.VM_USERNAME,
            "-gp",
            Prompts.VM_PASSWORD,
            command,
            self.path,
            *args
        ], text=True, capture_output=True, encoding="utf-8")

        success = completed.returncode in tolerance
        if not success:
            self.vlog.fallback().error(
                f"Executing failed on vmrun {command}: {completed.stderr}."
            )
        return (completed.stdout, success)

    def _list_snapshots(self) -> Optional[str]:
        output, success = self._vmrun("listSnapshots")
        return output if success else None

    def _create_snapshots(self, snapshot_name: str) -> bool:
        assert isinstance(snapshot_name, str)
        _, success = self._vmrun("snapshot", snapshot_name)
        return success

    # very hard to use, try task._execute() instead
    def _run(self, text: str, tolerance: Iterable[int] = []) -> bool:
        assert isinstance(text, str)
        return self._vmrun(
            "runScriptInGuest",
            "/bin/bash",
            text,
            tolerance=tolerance
        )

    def _request(self, query: str, param: Dict["str", Any]) -> requests.Response:
        # query string example: "POST:8080/api/version"
        # correspond to request.post(f"http://{base}:{port}{path}")
        reg_exp = r'(GET|POST)(:\d+)?(.+)'
        request_method, port, pathname = re.search(reg_exp, query).groups()
        if port is None:
            port = f":{VManager.SERVER_PORT}"

        request = getattr(requests, request_method.lower())
        base = f"http://{self.controller.vm_ip}"

        if request_method == "POST":
            if "headers" not in param:
                param["headers"] = {}
            # ``requests`` must generate the multipart boundary itself when a
            # file is attached.  Forcing application/json here makes Flask
            # see an empty ``request.files`` mapping.
            if "files" not in param and "Content-Type" not in param["headers"]:
                param["headers"]["Content-Type"] = "application/json"
        return request(
            base + port + pathname,
            timeout=self.HOMO_TIMEOUT,
            **param
        )

    @_env_handler
    def __call__(self, code: str) -> None:
        assert isinstance(code, str)
        self.controller.execute_python_command(code)

    @_env_handler
    def revert(self, snapshot_name: str) -> bool:
        assert isinstance(snapshot_name, str)

        self.vlog.info(f"Revert to snapshot of {snapshot_name}.")
        try:
            self.env.snapshot_name = snapshot_name
            self.env._revert_to_snapshot()
            self.env._start_emulator()
            # A recreated Docker container can receive a different bridge IP.
            # Refresh application-specific REST clients after every reset.
            self._post__enter__()
            return True
        except Exception as err:
            self.vlog.error(f"Desktop reset failed: {err}")
            return False

    def __enter__(self) -> Self:
        global ENVS
        assert not self.entered
        ENVS[self.key] = ENVS[self.key]()
        return super().__enter__()

    @_env_handler
    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.env.close()
        ENVS[self.key] = self._env_factory
        super().__exit__(exc_type, exc_value, traceback)

    @_env_handler
    @Manager._assert_handler
    def textual(self) -> Optional[str]:
        return self.controller.get_terminal_output()

    @_env_handler
    @Manager._assert_handler
    def screenshot(self) -> Optional[Image.Image]:
        raw_screenshot = self.controller.get_screenshot()
        return Image.open(BytesIO(raw_screenshot))

    @_env_handler
    @Manager._assert_handler
    def a11y_tree(self) -> Optional[str]:
        raw_a11y_tree = self.controller.get_accessibility_tree()
        a11y_tree = utils.linearize(raw_a11y_tree)
        if a11y_tree:
            a11y_tree = utils.trim(a11y_tree, self.a11y_tree_limit)
        return a11y_tree

    @_env_handler
    def set_of_marks(self) -> Union[Tuple[Image.Image, str], NoReturn]:
        # a11y tree consumes more time than screenshot
        # env may change if screenshot is taken in advance
        raw_a11y_tree = self.controller.get_accessibility_tree()
        raw_screenshot = self.controller.get_screenshot()

        # controller does not check nullity
        assert raw_a11y_tree is not None
        assert raw_screenshot is not None

        tags_info, _, som, a11y_tree = utils.tag_screenshot(raw_screenshot, raw_a11y_tree)
        return (
            tags_info,
            Image.open(BytesIO(som)),
            utils.trim(a11y_tree, self.a11y_tree_limit)
        )

    @_env_handler
    def show_som(self) -> None:
        self.set_of_marks()[1].show()

    @_env_handler
    def record_start(self) -> None:
        self.controller.start_recording()

    @_env_handler
    def record_stop(self, dest_path: str) -> None:
        self.controller.end_recording(dest_path)

    @_env_handler
    @error_factory(None)
    def read_file(self, file_path: str) -> Optional[str]:
        response = self._request(f"GET/read", {
            "params": {
                "path": file_path.replace("\\", "/")
            }
        })
        response.raise_for_status()
        return response.text

    @_env_handler
    @error_factory(False)
    def write_file(self, file_path: str, data: str) -> bool:
        response = self._request(f"POST/write", {
            "json": {
                "path": file_path.replace("\\", "/"),
                "content": data
            }
        })
        return response.text == "OK"

    @_env_handler
    @error_factory(False)
    def append_file(self, file_path: str, data: str) -> bool:
        response = self._request(f"POST/append", {
            "json": {
                "path": file_path.replace("\\", "/"),
                "content": data
            }
        })
        return response.text == "OK"

    @_env_handler
    @error_factory(False)
    def upload_file(self, source_path: str, file_path: str) -> bool:
        with open(source_path, "rb") as readable:
            response = self._request("POST/setup/upload", {
                "data": {"file_path": file_path.replace("\\", "/")},
                "files": {"file_data": readable},
            })
        return response.status_code == 200
