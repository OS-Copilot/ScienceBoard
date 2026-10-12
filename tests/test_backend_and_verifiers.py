from __future__ import annotations

import unittest
from argparse import Namespace
from types import SimpleNamespace
from unittest.mock import patch

import main
from sci.Tester import TaskGroup, TaskInfo
from sci.ChimeraX.task import TaskMixin as ChimeraVerifier
from sci.base.model import TextContent
from sci.base.prompt import CodeLike
from sci.base.utils import TypeSort
from sci.vm.vmanager import ENVS, VManager


class FakeDesktopEnv:
    def __init__(self) -> None:
        self.controller = SimpleNamespace(vm_ip="127.0.0.1")
        self.snapshot_name = "sci_bench"
        self.closed = False

    def close(self) -> None:
        self.closed = True


class DockerManagerLifecycleTests(unittest.TestCase):
    def manager(self) -> VManager:
        manager = VManager(
            version="0.1",
            provider_name="docker",
            docker_image="unused:test",
        )
        manager._env_factory = FakeDesktopEnv
        ENVS[manager.key] = manager._env_factory
        return manager

    def test_manager_can_be_reentered(self) -> None:
        manager = self.manager()
        with manager:
            self.assertTrue(manager.entered)
        self.assertFalse(manager.entered)
        with manager:
            self.assertTrue(manager.entered)
        self.assertFalse(manager.entered)

    def test_equal_configs_have_independent_lifecycles(self) -> None:
        first = self.manager()
        second = self.manager()
        self.assertNotEqual(first.key, second.key)
        with first:
            self.assertTrue(first.entered)
            self.assertFalse(second.entered)
        with second:
            self.assertTrue(second.entered)

    def test_docker_manager_construction_never_calls_vmrun(self) -> None:
        with patch.object(VManager, "_vmrun", side_effect=AssertionError("vmrun used")):
            manager = self.manager()
        self.assertFalse(manager.entered)

    def test_vm_apps_are_separate_lifecycle_groups(self) -> None:
        items = []
        for app in ("Celestia", "Lean"):
            item = object.__new__(TaskInfo)
            item.task = SimpleNamespace(
                type_sort=TypeSort(app, TypeSort.Sort.VM)
            )
            items.append(item)
        self.assertEqual(len(TaskGroup(items).groups), 2)


class DockerConfigurationTests(unittest.TestCase):
    def test_docker_check_does_not_require_vmware(self) -> None:
        args = Namespace(
            tasks="tasks/VM/KAlgebra/A-01.json",
            model="test_model",
            mode="docker",
            docker_image="scienceboard:test",
            vm_path=None,
        )
        completed = SimpleNamespace(
            returncode=0,
            stdout=(
                '{"Architecture":"amd64","Config":{"Labels":'
                '{"org.scienceboard.version":"0.1",'
                '"org.scienceboard.distribution":"sanitized-flat"}}}'
            ),
        )
        with (
            patch.object(main, "MODEL_ENV", {"test_model": ()}),
            patch.object(main.shutil, "which", side_effect=lambda name: "/usr/bin/docker" if name == "docker" else None) as which,
            patch.object(main.subprocess, "run", return_value=completed),
        ):
            self.assertEqual(main.configuration_issues(args), [])
        self.assertEqual([call.args[0] for call in which.call_args_list], ["docker", "docker"])

    def test_docker_check_rejects_unflattened_image(self) -> None:
        args = Namespace(
            tasks="tasks/VM/KAlgebra/A-01.json",
            model="test_model",
            mode="docker",
            docker_image="scienceboard-layered:test",
            vm_path=None,
        )
        completed = SimpleNamespace(
            returncode=0,
            stdout=(
                '{"Architecture":"amd64","Config":{"Labels":'
                '{"org.scienceboard.version":"0.1"}}}'
            ),
        )
        with (
            patch.object(main, "MODEL_ENV", {"test_model": ()}),
            patch.object(main.shutil, "which", return_value="/usr/bin/docker"),
            patch.object(main.subprocess, "run", return_value=completed),
        ):
            self.assertIn(
                "Docker image must be a sanitized-flat distribution",
                main.configuration_issues(args),
            )


class ChimeraVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = object.__new__(ChimeraVerifier)
        self.verifier.vlog = SimpleNamespace(info=lambda _message: None)

    def test_direct_null_check_is_not_vacuously_true(self) -> None:
        item = {"key": "target", "value": None}
        self.assertFalse(self.verifier._eval_states(item, {"target": 1}))
        self.assertTrue(self.verifier._eval_states(item, {}))

    def test_find_null_check_uses_matching_keys(self) -> None:
        item = {
            "find": "lambda key, value: value == 'needle'",
            "key": "lambda key: key",
            "value": None,
        }
        self.assertFalse(self.verifier._eval_states(item, {"one": "needle"}))
        self.assertTrue(self.verifier._eval_states(item, {"one": "other"}))

    def test_find_accepts_any_matching_transformed_value(self) -> None:
        item = {
            "find": "lambda key, value: key.endswith('.name')",
            "key": "lambda key: key.replace('.name', '.value')",
            "value": 2,
        }
        state = {
            "a.name": "first",
            "a.value": 1,
            "b.name": "second",
            "b.value": 2,
        }
        self.assertTrue(self.verifier._eval_states(item, state))

    def test_info_comparison_preserves_multiplicity(self) -> None:
        self.verifier.manager = SimpleNamespace(
            _call=lambda _command: (["same\nother"], True)
        )
        item = {"key": "atoms", "value": ["same", "same"]}
        self.assertFalse(self.verifier._eval_info(item, {}))

    def test_unavailable_application_state_fails_closed(self) -> None:
        self.verifier.manager = SimpleNamespace(
            states_dump=lambda: (_ for _ in ()).throw(ConnectionError("closed"))
        )
        self.verifier.evaluate = [{"type": "states", "key": "x", "value": 1}]
        self.assertFalse(self.verifier.eval())


class PromptParserTests(unittest.TestCase):
    def test_fenced_primitive_keeps_argument(self) -> None:
        codes = CodeLike.extract_antiquot(
            TextContent("```ANS 1966-047A```"), {"ANS"}, None
        )
        self.assertEqual([item.code for item in codes], ["ANS 1966-047A"])

    def test_fenced_language_tag_is_removed(self) -> None:
        codes = CodeLike.extract_antiquot(
            TextContent("```python\nprint('ok')\n```"), set(), None
        )
        self.assertEqual([item.code for item in codes], ["print('ok')"])

    def test_fenced_wait_keeps_duration(self) -> None:
        codes = CodeLike.extract_antiquot(
            TextContent("```WAIT 3```"), {"WAIT"}, None
        )
        self.assertEqual([item.code for item in codes], ["WAIT 3"])


if __name__ == "__main__":
    unittest.main()
