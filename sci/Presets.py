import sys
import os
import shlex

from typing import Optional, Dict, Any
from typing import Callable, TypeAlias

sys.dont_write_bytecode = True
from . import TypeSort

# preserved for potential comman kwargs
# all args should have a default value
# should be consisted with Prompts' lambda
# add lambda function for lazy loading
Config: TypeAlias = Dict[TypeSort, Callable[[], Dict[str, Any]]]
def spawn_managers(
    vm_headless: bool = False,
    vm_path: Optional[str] = None
) -> Config:
    return {
        TypeSort.VM: lambda: {
            "version": "0.1",
            "vm_path": vm_path,
            "headless": vm_headless,
            "port": 8000
        },
        TypeSort.Raw("ChimeraX"): lambda: {
            "version": "0.5",
            "sort": "daily",
            "port": 8000,
            "gui": True
        },
        TypeSort.Raw("KAlgebra"): lambda: {
            "version": "1.0",
            "bin_path": os.environ["KALG_BIN_PATH"],
            "lib_path": os.environ["QT6_LIB_PATH"],
            "port": 8000
        },
        TypeSort.Raw("Celestia"): lambda: {
            "version": "1.0",
            "bin_path": os.environ["CELE_BIN_PATH"],
            "lib_path": os.environ["QT6_LIB_PATH"],
            "port": 8000
        },
        TypeSort.Raw("GrassGIS"): lambda: {
            "version": "0.1",
            "bin_path": os.environ["GIS_BIN_PATH"],
            "lib_path": os.environ["FFI_LIB_PATH"],
            "data_path": os.path.expanduser("~/grassdata"),
            "port": 8000
        },
        TypeSort.Raw("TeXstudio"): lambda: {
            "version": "0.1"
        },
        TypeSort.Raw("Lean"): lambda: {
            "version": "0.1",
            "lib_path": os.environ["LEAN_LIB_PATH"],
        }
    }


def spawn_docker_managers(
    _headless: bool = True,
    docker_image: Optional[str] = None,
) -> Config:
    """Return VM-task manager arguments backed by a Docker container.

    The callable deliberately has the same two-argument shape as
    ``spawn_managers`` because ``Tester`` treats provider configuration as a
    dependency-injected factory.
    """
    if not docker_image:
        raise ValueError("DOCKER_IMAGE (or --docker-image) is required")

    return {
        TypeSort.VM: lambda: {
            "version": "0.1",
            # Tester retains the legacy vm_path field for VM-sort tasks.  The
            # manager receives an explicit image/backend so it never treats
            # this value as a host filesystem path.
            "vm_path": docker_image,
            "docker_image": docker_image,
            "provider_name": "docker",
            "headless": True,
            "port": 8000,
            "docker_binary": os.environ.get("DOCKER_BINARY", "docker"),
            "docker_startup_timeout": int(
                os.environ.get("DOCKER_STARTUP_TIMEOUT", "240")
            ),
            "docker_run_args": shlex.split(
                os.environ.get("DOCKER_RUN_ARGS", "")
            ),
        },
    }

def spawn_modules(manager_args: Optional[Config] = None):
    from . import ChimeraX
    from . import KAlgebra
    from . import Celestia
    from . import GrassGIS
    from . import TeXstudio
    from . import Lean

    frozen = locals()
    if manager_args == None:
        manager_args = spawn_managers()

    return {
        type_sort.type: frozen[type_sort.type]
        for type_sort in manager_args
        if type_sort.sort == TypeSort.Sort.Raw
    }
