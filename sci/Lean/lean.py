import sys
import os
import json
import subprocess

from typing import Dict, List, Union
from typing import Callable, Self

sys.dont_write_bytecode = True
from ..base import utils
from ..base import Manager, PromptFactory
from ..vm import VManager
from .format import *


# simple encapsulation of Lean REPL
class RawManager(Manager):
    Message = Dict[str, Union[str, int]]
    REPL_URL = "https://github.com/leanprover-community/repl"
    TIMEOUT = 120
    READY_FILENAME = ".scienceboard-ready"

    # lower version NG (e.g. v4.9.0)
    VERSION_MAP = {
        "0.1": {
            "tag": "v4.14.0"
        }
    }

    def __init__(
        self,
        version: str = "0.1",
        lib_path: str = None
    ) -> None:
        # this assertion is prior to __check_version()
        assert version in RawManager.VERSION_MAP
        super().__init__(version)

        assert isinstance(lib_path, str) and lib_path
        self.lib_path = os.path.abspath(os.path.expanduser(lib_path))
        self.cwd_path = os.path.join(self.lib_path, "test/Mathlib")

        self.set_headers(lambda _: [])
        self.history: List[Union[REPLOutput, REPLOutputTactic]] = []

        # Download REPL and Mathlib. A checkout alone is not sufficient because
        # setup may have been interrupted before the build artifacts existed.
        if not os.path.exists(os.path.join(self.lib_path, ".git")):
            self.__fetch()
        self.__version()
        if not os.path.exists(os.path.join(self.lib_path, self.READY_FILENAME)):
            self.__build()

    def set_headers(self, func: Callable) -> None:
        setattr(self.__class__, "headers", property(func))

    def __fetch(self) -> None:
        assert os.system(f"git clone {RawManager.REPL_URL} {self.lib_path}") == 0

    def __build(self) -> None:
        with utils.temp_chdir(self.lib_path):
            assert os.system("lake build repl") == 0

        with utils.temp_chdir(self.cwd_path):
            assert os.system("lake exe cache get") == 0
            assert os.system("lake build Mathlib") == 0

        open(
            os.path.join(self.lib_path, self.READY_FILENAME),
            mode="w",
            encoding="utf-8"
        ).close()

    def __version(self):
        tag_name = RawManager.VERSION_MAP[self.version]["tag"]
        with utils.temp_chdir(self.lib_path):
            assert os.system(f"git checkout tags/{tag_name} --quiet") == 0

    def __read(self) -> Dict:
        raw_outputs = ""
        read_line = lambda: self.process.stdout.readline()

        while (line := read_line()) == "\n": ...
        raw_outputs += line

        while (line := read_line()) != "\n":
            raw_outputs += line
        return json.loads(raw_outputs)

    def _call(self, query: Message, tactic_only: bool = False) -> REPLOutput:
        input = REPLInput.from_dict(query)
        output = None
        force = lambda input: ("sorry" in input.tactic) or ("admit" in input.tactic)

        if (isinstance(input, REPLInputTactic) and not force(input)) \
            or (not tactic_only and isinstance(input, REPLInputCommand)):
            self.process.stdin.write(input.dumps())
            self.process.stdin.flush()
            output = REPLOutput.from_dict(input=input, output=self.__read())

        else:
            message = "Could not apply `sorry` or `admit` in tactic mode." \
                if (isinstance(input, REPLInputTactic) and force(input)) \
                else "Could not parse as a valid JSON tactic."
            output = REPLOutput(input=query, message=message)

        return output

    def __call__(self, tactic: str) -> bool:
        try:
            tactic = json.loads(tactic)
        except: ...
        output = self._call(tactic, tactic_only=True)

        # panic here will cause skipping of the whole task
        # but if this happened, there might be sth going wrong
        assert type(output) in (REPLOutput, REPLOutputTactic)
        self.history.append(output)

        return not output.is_error()

    def __enter__(self) -> Self:
        self.process = subprocess.Popen(
            "lake env ../../.lake/build/bin/repl",
            shell=True,
            cwd=self.cwd_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8"
        )

        self.history.clear()
        return super().__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.process.kill()
        return super().__exit__(exc_type, exc_value, traceback)

    def textual(self) -> str:
        history_info = "\n".join([item.dumps() for item in self.history])
        if len(history_info) > 0:
            history_info = "Historical interactive records: \n" + history_info

        return "\n\n".join([
            *PromptFactory.filter(self.headers),
            *PromptFactory.option(history_info)
        ])


class VMManager(VManager):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
