import sys
import os
import re
import copy
import shutil
import inspect
import tempfile
import traceback

from dataclasses import dataclass

from typing import Union, Optional, List, Set, Dict, Any
from typing import Iterable, Callable, Generator, FrozenSet
from typing import TypeVar, TypedDict, Unpack, NotRequired

sys.dont_write_bytecode = True
from . import TypeSort
from . import Model, ModelType
from . import Agent, AIOAgent, Community
from . import Manager, VManager, Task
from . import Log, VirtualLog
from . import OBS, Presets

POLY = TypeVar("POLY")

@dataclass
class Counter:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    ignored: int = 0
    vlog: VirtualLog = VirtualLog()

    def _pass(self) -> None:
        self.passed += 1
        self.vlog.info("\033[1mTask finished with passed=TRUE.\033[0m")

    def _fail(self) -> None:
        self.failed += 1
        self.vlog.info("\033[1mTask finished with passed=FALSE.\033[0m")

    def _skip(self) -> None:
        self.skipped += 1
        self.vlog.error("Task testing failed; skipped.\n" + traceback.format_exc())

    def _ignore(self) -> None:
        self.ignored += 1
        self.vlog.info("Task already finished; ignored.")
        self.vlog.register(Log.delete)

    def __str__(self) -> str:
        total = self.passed + self.failed + self.skipped + self.ignored
        return (
            f"{total} total tested: "
            f"{self.passed} passed, "
            f"{self.failed} failed, "
            f"{self.skipped} skipped, "
            f"{self.ignored} ignored."
        )

    def __repr__(self) -> str:
        return "\033[1m" + self.__str__() + "\033[0m"

    def callback(self) -> None:
        self.vlog.info(self.__repr__())


# type annotation for Automata
class AutomataType(TypedDict):
    model_style: ModelType
    base_url: str
    model_name: str
    api_key: NotRequired[Optional[str]]
    proxy: NotRequired[Optional[str]]
    version: NotRequired[Optional[str]]
    max_tokens: NotRequired[Optional[int]]
    top_p: NotRequired[Optional[float]]
    temperature: NotRequired[Optional[float]]
    overflow_style: NotRequired[Optional[str]]
    context_window: NotRequired[int]
    hide_text: NotRequired[bool]
    code_style: NotRequired[str]


# Automata receive keyword args from Model and Agent
# register is used for post-processing
class Automata:
    def __init__(
        self,
        register: Union[Callable, List[Callable]] = [],
        **kwargs: Unpack[AutomataType]
    ) -> None:
        if isinstance(register, Iterable):
            for handler in register:
                assert hasattr(handler, "__call__")
            self.register = register
        else:
            assert hasattr(register, "__call__")
            self.register = [register]

        if "model" in kwargs:
            del kwargs["model"]

        model_params = list(Model.__dataclass_fields__.keys())
        agent_params = list(inspect.signature(Agent).parameters)
        for key in kwargs:
            assert key in model_params or key in agent_params

        self.model_args = {
            key: value for key, value in kwargs.items()
            if key in model_params
        }

        self.agent_args = {
            key: value for key, value in kwargs.items()
            if key in agent_params
        }

    def __call__(self, agent_cls: POLY = AIOAgent) -> POLY:
        model = Model(**self.model_args)
        agent = agent_cls(model=model, **self.agent_args)
        for handler in self.register:
            handler(agent)
        return agent

    # insert <IMAGE_TOKEN> for DeepSeek-VL AIOAgent
    # usage #1: Automata(register=Automata.image_token(), ...)
    # usage #2: Automata(register=[Automata.image_token(), ...], ...)
    @staticmethod
    def image_token(tag: str = "<IMAGE_TOKEN>") -> Callable[[AIOAgent], None]:
        def _image_token(agent: AIOAgent) -> None:
            assert isinstance(tag, str)
            agent.USER_OPENING = copy.deepcopy(AIOAgent.USER_OPENING)
            for key in agent.USER_OPENING:
                if key == frozenset({OBS.screenshot}):
                    agent.USER_OPENING[key] += (tag + "\n")
                elif OBS.screenshot in key:
                    agent.USER_OPENING[key] = re.sub(
                        "screenshot",
                        f"screenshot {tag}",
                        agent.USER_OPENING[key]
                    )
        return _image_token

    def prompt(self, obs: FrozenSet[str], type_sort: TypeSort) -> str:
        return self().prompt_factory(obs, type_sort)("...")


class TaskInfo:
    def __init__(self, task: Task, infix: str = "") -> None:
        assert isinstance(task, Task)
        self.task = task

        assert isinstance(infix, str)
        self.infix = infix

    @property
    def ident(self):
        identifier = os.path.join(self.infix, self.task.name)
        if sys.platform == "win32":
            identifier.replace("\\", "/")
        return identifier

    def __lt__(self, __value: "TaskInfo") -> bool:
        left, right = self.task, __value.task
        return left.sort < right.sort or \
            (left.sort == right.sort and left.type < right.type)

    def __repr__(self) -> str:
        return f"{self.ident}: {self.task.sort}.{self.task.type}"

    def __call__(self) -> bool:
        return self.task()

    # return True if the task has not been finished
    def snoop(self, base_path: str) -> bool:
        return not os.path.exists(os.path.join(
            base_path,
            self.ident,
            Log.RESULT_FILENAME
        ))


class TaskGroup:
    def __init__(self, raw: List[TaskInfo]) -> None:
        assert isinstance(raw, list)
        self.groups: List[List[TaskInfo]] = []

        last_info = None
        for task_info in raw:
            assert isinstance(task_info, TaskInfo)
            if last_info is not None \
                and task_info.task.type_sort == last_info.task.type_sort:
                self.groups[-1].append(task_info)
            else:
                self.groups.append([task_info])
            last_info = task_info

    def __check(self) -> None:
        for group in self.groups:
            assert len(group) > 0
            for task_info in group:
                first = group[0].task.manager
                current = task_info.task.manager
                if first != current:
                    assert VManager in first.__class__.mro() \
                        and VManager in current.__class__.mro()

    def __call__(self, base_path: str, ignore: bool) -> Generator:
        assert isinstance(base_path, str)
        assert isinstance(ignore, bool)
        self.__check()

        for group in self.groups:
            has_unfinished = any([item.snoop(base_path) for item in group])
            if has_unfinished or not ignore:
                with group[0].task.manager:
                    for task_info in group:
                        yield task_info
            else:
                for task_info in group:
                    yield task_info


class Tester:
    SHUTDOWN_INTERVAL = 10

    def __init__(
        self,
        tasks_path: str,
        logs_path: str,
        community: Community,
        obs_types: Set[str] = {OBS.screenshot},
        vm_path: Optional[str] = None,
        headless: bool = False,
        parallel: bool = False,
        ignore: bool = True,
        debug: bool = False,
        optimize: bool = True,
        relative: bool = False,
        handle_managers: Callable = Presets.spawn_managers
    ) -> None:
        assert isinstance(tasks_path, str)
        tasks_path = os.path.expanduser(tasks_path)
        assert os.path.exists(tasks_path)

        if os.path.isfile(tasks_path):
            self.__temp_dir = tempfile.TemporaryDirectory()
            task_filename = os.path.split(tasks_path)[1]
            new_path = os.path.join(self.__temp_dir.name, task_filename)

            shutil.copyfile(tasks_path, new_path)
            self.tasks_path = self.__temp_dir.name
        else:
            self.__temp_dir = None
            self.tasks_path = tasks_path

        # process log first
        assert isinstance(logs_path, str)
        logs_path = os.path.expanduser(logs_path)
        os.makedirs(logs_path, exist_ok=True)
        self.logs_path = logs_path

        # all run-time error / assertion error
        # should be caught in __traverse() & __call()
        # in fact, self.log call inside of tester.__call()
        # should be converted into the form of vlog.info()
        self.log = Log()

        assert isinstance(community, Community)
        self.community = community
        self.community.vlog.set(self.log)
        for _, agent in self.community:
            agent.vlog.set(self.log)

        assert isinstance(obs_types, Iterable)
        self.obs_types = obs_types

        if isinstance(vm_path, str):
            vm_path = os.path.expanduser(vm_path)
        else:
            assert vm_path is None
        self.vm_path = vm_path

        # manager in managers should not be Manager itself
        assert hasattr(handle_managers, "__call__")
        self.manager_args = handle_managers(headless, parallel, vm_path)
        self.managers = {}
        self.modules = Presets.spawn_modules()

        assert isinstance(ignore, bool)
        self.ignore = ignore

        assert isinstance(debug, bool)
        self.debug = debug

        assert isinstance(optimize, bool)
        self.optimize = optimize

        assert isinstance(relative, bool)
        self.relative = relative

        self.task_info: List[TaskInfo] = []
        self.__traverse()
        self.task_group = TaskGroup(sorted(self.task_info))

    def __del__(self) -> None:
        if self.__temp_dir is not None:
            self.__temp_dir.cleanup()

    def __manager(self, type_sort: TypeSort):
        # add __str__() to differentiate all managers
        if str(type_sort) in self.managers:
            return self.managers[str(type_sort)]

        manager_class = getattr(
            self.modules[type_sort.type],
            type_sort(Manager.__name__)
        )

        manager_args = self.manager_args[type_sort]()
        manager = manager_class(**manager_args)
        self.managers[str(type_sort)] = manager
        manager.vlog.set(self.log)
        return manager

    def __load(self, config_path: str) -> Task:
        # using nil agent & manager only to load type field
        type_sort = Task(config_path=config_path).type_sort
        if type_sort.sort == TypeSort.Sort.VM:
            assert self.vm_path is not None

        task_class = getattr(
            self.modules[type_sort.type],
            type_sort(Task.__name__)
        )

        return task_class(
            config_path=config_path,
            manager=self.__manager(type_sort),
            community=self.community,
            obs_types=self.obs_types,
            debug=self.debug,
            relative=self.relative
        )

    def __traverse(self, current_infix: str = "") -> None:
        current_dir_path = os.path.join(self.tasks_path, current_infix)
        for unknown_name in sorted(os.listdir(current_dir_path)):
            unknown_path = os.path.join(current_dir_path, unknown_name)
            if os.path.isfile(unknown_path):
                try:
                    new_task = self.__load(unknown_path)
                    new_task.vlog.set(self.log)
                    self.task_info.append(TaskInfo(new_task, infix=current_infix))
                except Exception:
                    error_info = "Config loading failed; skipped: " \
                        + unknown_path \
                        + "\n" \
                        + traceback.format_exc()
                    self.log.error(error_info)
            else:
                self.__traverse(os.path.join(current_infix, unknown_name))

    @staticmethod
    def _log_handler(method: Callable) -> Callable:
        def _log_wrapper(self: "Tester"):
            local_counter = Counter()
            local_counter.vlog.set(self.log)
            self.log.trigger(
                self.logs_path,
                prefix=self.log.SUM_LOG_PREFIX,
                dependent=False
            )
            method(self, local_counter)
            local_counter.callback()
            self.log.callback()
            Manager.pause(Tester.SHUTDOWN_INTERVAL)
        return _log_wrapper

    # there is no need to pass counter
    # as decorator has done all for it
    @_log_handler
    def __call__(self, counter: Counter) -> None:
        generator = self.task_group(self.logs_path, self.ignore)
        for task_info in generator if self.optimize else self.task_info:
            with self.log(
                base_path=self.logs_path,
                ident=task_info.ident,
                ignore=self.ignore
            ) as result_exist:
                if result_exist:
                    counter._ignore()
                    continue
                try:
                    counter._pass() if task_info() else counter._fail()
                except Exception:
                    counter._skip()

    # alternative for multiple Tester(...)()
    @staticmethod
    def plan(params: List[Dict[str, Any]], check_only: bool = False) -> None:
        assert isinstance(params, list)
        for param in params:
            try:
                assert isinstance(param, dict)
                tester = Tester(**param)
                if not check_only:
                    tester()
            except Exception:
                traceback.print_exc()
