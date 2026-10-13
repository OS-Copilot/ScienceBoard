import sys
import os
import re
import time
import json
import zipfile
import requests
import subprocess
import urllib.request

from typing import List, Dict, Tuple, Optional
from typing import Callable, Self, Union

from PIL import Image
from PIL import ImageGrab

sys.dont_write_bytecode = True
from ..base import Manager
from ..vm import VManager

class ManagerMixin:
    def __init__(self) -> None:
        # this class is not independent: _execute() needed
        raise

    def _call(
        self: Union["RawManager", "VMManager"],
        command: str
    ) -> Tuple[List[str], bool]:
        response = self._execute(command)
        return (
            response["log messages"]["note"],
            response["error"] is None
        )


# raw: supposed that ChimeraX is pre-installed on Linux
#      and one of commands in SORT_MAP is runnable
class RawManager(Manager, ManagerMixin):
    SORT_MAP: Dict[str, List[str]] = {
        "stable": [
            "chimerax"
        ],
        "daily": [
            "chimerax-daily"
        ],
        "flatpak": [
            "flatpak",
            "run",
            "edu.ucsf.rbvi.ChimeraX"
        ]
    }
    TIMEOUT = 120  # GUI ChimeraX on macOS needs well over 15 s before the REST server line appears
    REST_FLAG: str = "REST server started"
    BASE_URL: Callable[[int], str] = lambda port: f"http://localhost:{port}/run"
    TOOL_URL: Callable[[str], str] = lambda version: \
        f"https://github.com/ShiinaHiiragi/chimerax-states/archive/refs/tags/{version}.zip"

    def __init__(
        self,
        version: str = "0.5",
        sort: str = "stable",
        path: Optional[str] = None,
        port: int = 8000,
        gui: bool = False
    ) -> None:
        super().__init__(version)

        assert sort in RawManager.SORT_MAP
        self.sort = sort

        assert path is None or os.path.exists(path)
        self.path = path

        assert port in range(1024, 65536)
        self.port = port

        assert isinstance(gui, bool)
        self.gui = gui

    def _execute(self, command: str) -> Dict:
        response = requests.get(
            RawManager.BASE_URL(self.port),
            params={"command": command},
            timeout=Manager.HOMO_TIMEOUT
        ).json()

        if response["error"] is not None:
            self.vlog.error(f"Failed when executing {command}: {response['error']}.")
        return response

    def __call__(self, command: str) -> None:
        self.__call(command)

    def states_dump(self) -> dict:
        timestamp = str(int(time.time() * 1000))
        assert self._call(f"states {self.temp_dir} {timestamp}")[1]
        return json.load(open(
            self.temp(f"{timestamp}.json"),
            mode="r",
            encoding="utf-8"
        ))

    def destroy_cli(self) -> bool:
        assert float(self.version) >= 0.3
        _, code = self._call("destroy")
        return code

    def clear_history(self) -> bool:
        assert float(self.version) >= 0.4
        _, code = self._call("clear")
        return code

    def __check_version(self) -> Optional[str]:
        version_pattern = r'[.\d]+'
        target_pattern = fr'SessionStates(\*\*)? \({version_pattern}\)'

        log_message, _ = self._call("toolshed list")
        bundle_list = log_message[1].split("\n")
        target_matched = [
            re.search(version_pattern, item)[0]
            for item in bundle_list
            if re.search(target_pattern, item)
        ]

        if len(target_matched) > 0:
            return target_matched[0]
        else:
            return None

    def __install_bundle(self, version: str, uninstall: bool = True) -> None:
        zip_file_path = self.temp(f"{version}.zip")
        bundle_dir_path = self.temp(f"chimerax-states-{version}")
        urllib.request.urlretrieve(RawManager.TOOL_URL(version), zip_file_path)

        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            zip_ref.extractall(self.temp_dir)

        if uninstall:
            assert self._call("toolshed uninstall SessionStates")[1]
        assert self._call(f"devel install {bundle_dir_path}")[1]

    def __prepare_env(self, desired_version: str) -> None:
        current_version = self.__check_version()
        if current_version != desired_version:
            self.__install_bundle(desired_version, current_version is not None)

    def __enter__(self) -> Self:
        nogui = [] if self.gui else ["--nogui"]
        startup_commands = [self.path] \
            if self.path is not None \
            else RawManager.SORT_MAP[self.sort]

        self.process = subprocess.Popen([
            *startup_commands,
            *nogui,
            "--cmd",
            f"remotecontrol rest start json true port {self.port}",
        ], stdout=subprocess.PIPE, text=True)

        timeout = time.time() + RawManager.TIMEOUT
        while True:
            if self.process.stdout.readline().startswith(RawManager.REST_FLAG):
                self.__prepare_env(self.version)
                return super().__enter__()
            assert time.time() <= timeout, "Timeout when opening ChimeraX"

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.process.kill()
        super().__exit__(exc_type, exc_value, traceback)

    def _linux_show_window(self) -> None:
        # to disable Pylance syntax checker
        assert sys.platform == "linux"
        from wmctrl import Window
        current_window = [
            window for window in Window.list()
            if window.pid == self.process.pid
        ][0]
        current_window.maximize()
        Manager.pause()

    def _win32_show_window(self) -> None:
        # to disable Pylance syntax checker
        assert sys.platform == "win32"
        import win32gui, win32con
        hwnd = win32gui.FindWindow(None, "ChimeraX")
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        Manager.pause()
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        Manager.pause()

    def screenshot(self) -> Image.Image:
        getattr(self, f"_{sys.platform}_show_window")()
        return ImageGrab.grab()


class VMManager(VManager, ManagerMixin):
    def __init__(
        self,
        *args,
        port: int = 8000,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        assert port in range(1024, 65536)
        self.port = port

    def _execute(self, command: str) -> Dict:
        return self._request(
            f"POST:{VManager.SERVER_PORT}/chimerax/run",
            param={"json": {"command": command}}
        ).json()

    def states_dump(self) -> dict:
        timestamp = str(int(time.time() * 1000))
        guest_dir = "/home/user/Downloads"
        guest_file = os.path.join(guest_dir, f"{timestamp}.json")

        assert self._call(f"states {guest_dir} {timestamp}")[1]
        return json.loads(self.read_file(guest_file))
