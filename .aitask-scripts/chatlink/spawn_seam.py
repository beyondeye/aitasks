"""Sandbox-launcher seam — protocol STUB (t1120_3; pinned contract 8).

This module defines only the seam *signature* the gateway daemon injects and
calls; **t1120_5 provides the real Docker backend** by promoting this
protocol into ``lib/sandbox_launch.py`` (its plan references this stub by
name — keep the names stable: ``SandboxSpec``, ``SandboxHandle``,
``launch``, ``reap_orphans``).

The seam is backend-agnostic and aligned with ``lib/launch_modes.py`` /
t562 semantics up front: workspace delivery by copy, sandbox named from
session identity (the ``session_id`` container label), headless
no-TTY, explicit cleanup verb. No process is ever constructed from a shell
string — ``agent_argv`` is an argv list (pinned contract 13).

:class:`FakeLauncher` is the deterministic test double (records specs,
scripted liveness) used by the t1120_3 test suite and by t1120_6's e2e
tests until the real backend lands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class LaunchError(Exception):
    """A sandbox could not be launched (surfaced as intake step-d failure)."""


@dataclass(frozen=True)
class SandboxSpec:
    """Everything a backend needs to launch one sandboxed agent.

    ``limits`` carries the clamped ceilings from ``ChatlinkConfig``
    (``memory``/``cpus``/``pids``/``wall_clock_s``); ``env_allowlist`` is
    the ONLY environment the agent receives (LLM key — never the bot token,
    never git credentials).
    """

    session_id: str
    relay_dir: str
    agent_argv: tuple = ()
    workspace_copy_path: str | None = None
    env_allowlist: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)


class SandboxHandle(Protocol):
    """A live (or finished) sandbox: liveness probe + kill + bounded wait."""

    def alive(self) -> bool: ...

    def wait(self, timeout: float | None = None) -> int | None:
        """Exit code, or ``None`` if still running at the deadline."""
        ...

    def kill(self) -> None: ...


class Launcher(Protocol):
    """The injectable seam the daemon consumes (contract 8)."""

    def launch(self, spec: SandboxSpec) -> SandboxHandle: ...

    def reap_orphans(self, workspace_id: str) -> list[str]:
        """Kill/remove orphaned sandboxes; returns live session_ids kept."""
        ...


class NullLauncher:
    """Production placeholder until t1120_5 lands the Docker backend.

    ``launch`` refuses honestly (the intake pipeline persists the failed
    session and annotates the thread); ``reap_orphans`` reports no live
    sessions, so startup reconciliation fail-closes anything left over.
    """

    def launch(self, spec: SandboxSpec) -> SandboxHandle:
        raise LaunchError(
            "no sandbox backend installed (Docker backend arrives with "
            "t1120_5)")

    def reap_orphans(self, workspace_id: str) -> list[str]:
        return []


# --------------------------------------------------------------------- #
# Test double
# --------------------------------------------------------------------- #


class FakeHandle:
    """Scripted handle: liveness/exit driven by the test."""

    def __init__(self, *, alive: bool = True, exit_code: int | None = None):
        self._alive = alive
        self._exit_code = exit_code

    def alive(self) -> bool:
        return self._alive

    def wait(self, timeout: float | None = None) -> int | None:
        return None if self._alive else self._exit_code

    def kill(self) -> None:
        self._alive = False
        if self._exit_code is None:
            self._exit_code = -9

    # test seam
    def finish(self, exit_code: int = 0) -> None:
        self._alive = False
        self._exit_code = exit_code


class FakeLauncher:
    """Records every launch; scriptable failures and live-session sets."""

    def __init__(self, *, fail_with: Exception | None = None,
                 live_session_ids: set | None = None):
        self.launched: list[SandboxSpec] = []
        self.handles: dict[str, FakeHandle] = {}
        self.reap_calls: list[str] = []
        self._fail_with = fail_with
        self._live = set(live_session_ids or ())

    def launch(self, spec: SandboxSpec) -> FakeHandle:
        if self._fail_with is not None:
            raise self._fail_with
        self.launched.append(spec)
        handle = FakeHandle(alive=True)
        self.handles[spec.session_id] = handle
        self._live.add(spec.session_id)
        return handle

    def reap_orphans(self, workspace_id: str) -> list[str]:
        self.reap_calls.append(workspace_id)
        return sorted(self._live)
