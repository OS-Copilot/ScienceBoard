import sys
import os
import re
import json
import traceback

from typing import List, Tuple, Set, Union, Optional
from typing import Any, Iterable, Callable, NoReturn

sys.dont_write_bytecode = True
from .agent import Primitive
from .community import Community
from .manager import OBS, Manager
from .log import Log, VirtualLog
from .utils import TypeSort, relative_py
from . import init

# base class for all tasks
# - subclass should include:
#   - __init__(): just check type and call super.__init__()
#   - _{func}(): functions used by init()
#   - @Task._stop_handler
#     eval(): evaluation of non-general eval-item
# - subclass can also include:
#   - check_config(): more assertion of config.json
#   - _init(): recover to init states of app
class Task:
    CONFIG_RETRY = 5
    ACTION_INTERVAL = 1
    EARLY_STOP = "stop"

    class PlannedNotImplemented(Exception):
        def __init__(self) -> None:
            ...

    def __init__(
        self,
        config_path: str,
        manager: Optional[Manager] = None,
        community: Optional[Community] = None,
        obs_types: Optional[Set[str]] = None,
        primitives: Set[str] = set(),
        debug: bool = False,
        relative: bool = False
    ) -> None:
        assert isinstance(config_path, str)
        config_path = os.path.expanduser(config_path)
        assert os.path.exists(config_path)
        self.path = config_path

        self.name = os.path.split(self.path)[1].split(".")[0]
        self.config = json.load(open(self.path, mode="r", encoding="utf-8"))

        assert manager is None or isinstance(manager, Manager)
        assert community is None or isinstance(community, Community)
        self.manager = manager
        self.community = community

        self.primitives = {
            item for item in Primitive.PRIMITIVES
            if not hasattr(getattr(Primitive, item), "__wrapped__")
        }.union(primitives)

        # remove primitive that has not been implemented
        self.primitives = {
            item for item in self.primitives if not(
                hasattr((primitive := getattr(Primitive, item)), "__dec__") \
                    and primitive.__dec__() == Primitive.virtual_handler \
                    and not hasattr(self.manager, item)
            )
        }

        self.__check_config()
        if self.__class__ != Task:
            assert self.version == self.manager.version
        if self.available:
            assert self.__class__.__name__.startswith(self.sort)

        # for RawTask: use textual() for CLI and screenshot() for GUI
        # for VMTask: use pre-defined observation set
        if obs_types is None:
            obs_types = {OBS.screenshot}

        assert isinstance(obs_types, Iterable)
        for obs_type in obs_types:
            assert obs_type in dir(Manager)

        if self.type_sort.sort == TypeSort.Sort.VM:
            self.obs_types = set(obs_types)
        elif manager is not None:
            self.obs_types = {OBS.screenshot if manager.is_gui else OBS.textual}

        assert isinstance(debug, bool)
        self.debug = debug

        assert isinstance(relative, bool)
        self.relative = relative

        self.vlog = VirtualLog()

    @property
    def available(self) -> bool:
        manager = getattr(self, "manager", None)
        community = getattr(self, "community", None)
        return manager is not None and community is not None

    def __check_config(self) -> None:
        assert "type" in self.config
        self.type = self.config["type"]
        assert isinstance(self.type, str)

        assert "sort" in self.config
        self.sort = self.config["sort"]
        assert self.sort in TypeSort.Sort._member_names_

        self.type_sort = TypeSort(
            self.type,
            TypeSort.Sort._member_map_[self.sort]
        )

        assert "steps" in self.config
        self.steps = self.config["steps"]
        assert isinstance(self.steps, int)

        assert "instruction" in self.config
        self.instruction = self.config["instruction"]
        assert isinstance(self.instruction, str)

        assert "version" in self.config
        self.version = self.config["version"]
        assert isinstance(self.version, str)

        assert "initialize" in self.config
        self.initialize = self.config["initialize"]
        assert isinstance(self.initialize, list)
        for init_item in self.initialize:
            assert isinstance(init_item, dict)
            assert "func" in init_item
            assert isinstance(init_item["func"], str)

        assert "evaluate" in self.config
        self.evaluate = self.config["evaluate"]
        assert isinstance(self.evaluate, list)
        for eval_item in self.evaluate:
            assert isinstance(eval_item, dict)
            assert "type" in eval_item
            if eval_item["type"] == Task.EARLY_STOP:
                assert "value" in eval_item
                assert isinstance(eval_item["value"], str)
                assert hasattr(Primitive, eval_item["value"])
                self.primitives.add(eval_item["value"])

                if eval_item["value"] == Primitive.ANS.__name__:
                    assert "args" in eval_item
                    assert isinstance(eval_item["args"], list)
                    for args_item in eval_item["args"]:
                        assert isinstance(args_item, str)

        self.ans = None
        if "ans" in self.config:
            self.ans = self.config["ans"]

        self.penalty = (2147438648, 0)
        if "penalty" in self.config:
            match_obj = re.search(r"(\d+):(\d+)", self.config["penalty"])
            self.penalty = (int(match_obj[1]), int(match_obj[2]))

    @staticmethod
    def _stop_handler(method: Callable) -> Callable:
        @Log.result_handler
        def _stop_wrapper(
            self,
            stop_type: staticmethod,
            stop_args: List[str]
        ) -> bool:
            try:
                return Task.eval(self, stop_type, stop_args)
            except Task.PlannedNotImplemented:
                return method(self)
        return _stop_wrapper

    @staticmethod
    def _avail_handler(method: Callable) -> Callable:
        def _avail_wrapper(self: "Task", *args, **kwargs) -> Any:
            assert self.available
            return method(self, *args, **kwargs)
        return _avail_wrapper

    @staticmethod
    def _config_handler(method: Callable) -> Callable:
        def _config_wrapper(self: "Task") -> None:
            for eval_item in self.evaluate:
                if eval_item["type"] == Task.EARLY_STOP:
                    continue
                method(self, eval_item)
        return _config_wrapper

    # do not use this method as much as posssible
    # try to customize each manager's own method of resetting
    def _init(self) -> bool:
        try:
            self.manager.__exit__(None, None, None)
            Manager.pause()
            self.manager.__enter__()
            return True
        except:
            return False

    # find local `func` first
    # then find `raw_func` or `vm_func` in .base.init
    # according to self.sort (in {"Raw", "VM"})
    @_avail_handler
    def init(self) -> bool:
        local_name = lambda func: f"_{func}"
        global_name = lambda func: f"{self.sort.lower()}_{func}"

        def func(func: str, wait: int = 0, **kwargs):
            handler = getattr(self, local_name(func)) \
                if hasattr(self, local_name(func)) \
                else getattr(init, global_name(func))

            if handler.__name__.startswith(TypeSort.Sort.VM.name.lower()):
                kwargs["manager"] = self.manager

            result = handler(**kwargs)
            Manager.pause(wait)
            return result

        # try `Task.CONFIG_RETRY` times
        # trigger assertion error if all fail
        for _ in range(Task.CONFIG_RETRY):
            feedback = True
            # set to init state from second try
            # if _init() failed, goto next iteration
            if not self._init():
                continue

            # try every init item in config file
            # if error occurred / do not return True
            # then stop init and retry in next iteration
            for init_item in self.initialize:
                Manager.pause()
                succeed = False
                try:
                    succeed = func(**init_item)
                except Exception:
                    self.vlog.error(
                        "Error when initializing."
                            + traceback.format_exc()
                    )
                finally:
                    if not succeed:
                        feedback = False
                        break

            # if any of item fails
            # feed back would not be True
            if feedback:
                return True
            else:
                continue
        return False

    def _step(self, step_index: int) -> bool:
        observation = {
            obs_type: getattr(self.manager, obs_type)()
            for obs_type in self.obs_types
        }

        # special cases: SoM -> SoM + A11y Tree
        nested_tags = None
        if OBS.set_of_marks in observation:
            nested_tags, som, a11y_tree = observation[OBS.set_of_marks]
            observation[OBS.a11y_tree] = a11y_tree
            observation[OBS.set_of_marks] = som

        # preserved action for multi-agents corporation
        response_codes = self.community(
            steps=(step_index, self.steps),
            inst=self.instruction,
            obs=observation,
            code_info=(self.primitives, nested_tags),
            type_sort=self.type_sort,
            timeout=self.manager.HETERO_TIMEOUT,
            manager=self.manager
        )

        # save the log first
        # becase primitives would cause exceptions
        self.vlog.save(
            step_index=step_index,
            obs=observation,
            codes=response_codes,
            community=self.community,
            is_textual=OBS.textual in observation
        )

        results = []
        for code_like in response_codes:
            if self.relative:
                code_like.push_prefix(relative_py, back=False)
            results.append(code_like(self.manager, self.primitives))
            Manager.pause()

        # Manager.__call__() return True/None if success/undecidable
        # if all code blocks fail, one liquidation is counted
        return all([item is False for item in results])

    # warning: this method will reset inner status of agents
    def __test_prompt(self) -> None:
        obs = frozenset({OBS.screenshot if self.manager.is_gui else OBS.textual})
        for name, agent in self.community:
            agent._init(
                obs,
                self.instruction,
                self.type_sort,
                self.primitives,
                self.manager
            )
            prompt = agent.system_message.content[0].text
            self.vlog.info(f"Prompt sample of {name}: \n" + prompt)

    @_avail_handler
    @Log.record_handler
    def predict(self) -> Tuple[staticmethod, List[str]]:
        try:
            liquid, step_index = 0, 0
            while step_index < self.steps:
                invalid = self._step(step_index)
                step_index += 1
                liquid += 1 if invalid else 0
                if liquid >= self.penalty[0]:
                    liquid = 0
                    self.steps -= self.penalty[1]
                    self.vlog.warning(
                        f"Total steps are reduced to {self.steps} "
                        f"due to {self.penalty[0]} consecutive incorrect inputs."
                    )
        except Primitive.PlannedTermination as early_stop:
            return early_stop.type, list(early_stop.args)
        return Primitive.TIMEOUT, []

    # in case Task().eval() is derectly called
    # if eval() of Task's subclass is called
    # result output will be written twice sometimes
    @_avail_handler
    @Log.result_handler
    def eval(
        self,
        stop_type: staticmethod,
        stop_args: List[str]
    ) -> Union[bool, NoReturn]:
        eval_index = 0

        while eval_index < len(self.evaluate):
            eval_item = self.evaluate[eval_index]
            if eval_item["type"] != Task.EARLY_STOP:
                eval_index += 1
            elif eval_item["value"] != stop_type.__name__:
                self.vlog.info(f"Evaluation failed at stop type.")
                return False
            elif eval_item["value"] == Primitive.ANS.__name__ \
                and eval_item["args"] != stop_args:
                self.vlog.info(f"Evaluation failed at ANS.")
                return False
            else:
                del self.evaluate[eval_index]

        if len(self.evaluate) > 0:
            raise Task.PlannedNotImplemented()
        else:
            return True

    def __call(self) -> bool:
        self.vlog.info("Starting initialization.")
        assert self.init(), "Fail to initialize the task"
        if self.debug:
            # input value will be converted to stop_type
            # default to TIMEOUT
            self.__test_prompt()
            if self.ans is not None:
                self.vlog.info(f"Answer: {self.ans}")
            primitive_text = self.vlog.input(
                f"Finish task manually: ",
                end=""
            ) or Primitive.TIMEOUT.__name__
            splits = primitive_text.split(" ")
            if hasattr(Primitive, splits[0]):
                stop_type, stop_args = getattr(Primitive, splits[0]), splits[1:]
            else:
                stop_type, stop_args = Primitive.TIMEOUT, []
        else:
            self.vlog.info("Starting prediction.")
            stop_type, stop_args = self.predict()
        self.vlog.info(f"Starting evaluation with stop type of {stop_type.__name__}.")
        return self.eval(stop_type, stop_args)

    @_avail_handler
    def __call__(self) -> bool:
        self.vlog.info(f"\033[1mTask: {self.instruction}\033[0m")
        if not self.manager.entered:
            with self.manager:
                return self.__call()
        else:
            self.manager._post__enter__()
            return self.__call()
