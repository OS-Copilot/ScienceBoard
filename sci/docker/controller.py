"""Controller compatibility layer for the containerized desktop service."""

from desktop_env.controllers.python import PythonController


class DockerController(PythonController):
    """The guest HTTP contract is intentionally identical to DesktopEnv's.

    Keeping a named class makes the provider boundary explicit and gives us a
    safe place for Docker-specific transport behavior without patching the
    third-party ``desktop-env`` package.
    """
