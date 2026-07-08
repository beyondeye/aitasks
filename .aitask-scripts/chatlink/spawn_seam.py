"""Compat re-export — the sandbox-launcher seam lives in
``lib/sandbox_launch.py`` (promoted by t1120_5 from the t1120_3 protocol
stub; pinned contract 8). Chatlink-internal imports and the t1120_3 test
suite keep using these names; new code should import ``lib.sandbox_launch``
directly (which also carries the Docker backend, the ``BACKENDS`` registry,
``make_workspace_copy`` and ``repo_identity``).

Importing any ``chatlink.*`` module requires ``.aitask-scripts`` on
``sys.path``, which is exactly what resolves ``lib.sandbox_launch`` here.
"""
from lib.sandbox_launch import (  # noqa: F401
    FakeHandle,
    FakeLauncher,
    LaunchError,
    Launcher,
    NullLauncher,
    SandboxHandle,
    SandboxSpec,
)

__all__ = [
    "FakeHandle",
    "FakeLauncher",
    "LaunchError",
    "Launcher",
    "NullLauncher",
    "SandboxHandle",
    "SandboxSpec",
]
