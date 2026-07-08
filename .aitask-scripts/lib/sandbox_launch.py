"""Backend-agnostic sandbox-launcher seam + Docker backend (t1120_5).

Promoted from the t1120_3 protocol stub ``chatlink/spawn_seam.py`` (which
now re-exports these names for compatibility — pinned contract 8 keeps
``SandboxSpec``, ``SandboxHandle``, ``launch``, ``reap_orphans`` stable).
The seam is aligned with ``lib/launch_modes.py`` / t562 semantics: workspace
delivery by copy, sandbox named from session identity, headless no-TTY,
explicit cleanup verb. t562's openshell modes are the planned second
backend of the ``BACKENDS`` registry below.

Seam contract (implemented by every backend):

- **Mounts**: the disposable workspace copy is mounted at ``/work`` (the
  working directory); the relay session dir is mounted read-write at
  ``/relay/<session_id>`` — the basename MUST stay the session id because
  the relay lib derives and validates the id from the dir name
  (``SessionDir.session_id``). A non-container backend uses the host paths
  directly. The container runs as the gateway's uid:gid (``HOME=/tmp``) so
  files it creates on the bind mounts stay removable by the gateway's
  cleanup.
- **Environment**: the agent receives ``CHATLINK_RELAY_DIR`` (the relay
  mount) and ``CHATLINK_BUG_REPORT_FILE`` (``<relay>/bug_report.md`` — the
  gateway writes the report into the session spool dir; extra named files
  there are tolerated by the gateway, which reads only ``question-*`` /
  ``answer-*`` / ``payload.json``), plus ``spec.env_allowlist`` merged on
  top. The allowlist is the ONLY caller-supplied environment (LLM API key —
  never the bot token, never git credentials).
- **Ownership labels** (stateless orphan discovery, gateway-death safe):
  ``ait.chatlink.session`` / ``ait.chatlink.workspace`` /
  ``ait.chatlink.repo`` / ``ait.chatlink.deadline``. The repo label scopes
  ownership to THIS checkout (two repos' gateways may share a chat
  workspace id — a foreign-repo container is never enumerated, killed, or
  counted live). The deadline label is the wall-clock cap as an epoch so a
  restarted gateway can reap past-cap containers with no local state.
- **Death signalling**: ``spec.on_death`` is invoked AT MOST ONCE, from the
  backend's watchdog thread, with the session_id, when the sandbox is
  observed dead (or right after a wall-clock kill). The callback must be
  thread-safe and non-blocking — chatlink supplies a
  ``loop.call_soon_threadsafe`` enqueue; ALL durable mutations (cancelled
  answers, record state, platform cleanup) run daemon-side through the
  sequential dispatch + executor phase discipline, never here. A raising
  callback is swallowed (startup reconciliation is the backstop).
- **Reap semantics** (``reap_orphans``): exited containers are removed;
  running ones past their deadline label (or with a malformed deadline —
  fail-closed) are killed and removed; the remaining running session_ids
  are returned as the LIVE set (startup reconciliation fail-closes every
  non-terminal record not in it). A running container whose session record
  is already terminal is deliberately NOT reaped here (reap is stateless);
  it dies at its deadline at the latest — a documented bounded leak.

No process is ever constructed from a shell string — ``agent_argv`` and
every docker invocation are argv lists (pinned contract 13).

:class:`FakeLauncher` is the deterministic test double (records specs,
scripted liveness) used by the chatlink test suite.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol

VALID_SANDBOX_BACKENDS: frozenset[str] = frozenset({"docker"})
DEFAULT_SANDBOX_BACKEND: str = "docker"
#: Image contract: built from ``.aitask-scripts/chatlink/docker/Dockerfile``
#: (see its header for the build command and refresh policy).
DEFAULT_SANDBOX_IMAGE: str = "ait-chatlink-agent"

LABEL_SESSION = "ait.chatlink.session"
LABEL_WORKSPACE = "ait.chatlink.workspace"
LABEL_REPO = "ait.chatlink.repo"
LABEL_DEADLINE = "ait.chatlink.deadline"

#: Watchdog poll cadence (seconds); injectable per-launcher for tests.
WATCHDOG_POLL_S = 2.0


class LaunchError(Exception):
    """A sandbox could not be launched (surfaced as intake step-d failure)."""


@dataclass(frozen=True)
class SandboxSpec:
    """Everything a backend needs to launch one sandboxed agent.

    ``limits`` carries the clamped ceilings from ``ChatlinkConfig``
    (``memory``/``cpus``/``pids``/``wall_clock_s``); ``env_allowlist`` is
    the ONLY caller-supplied environment the agent receives (LLM key —
    never the bot token, never git credentials). ``on_death`` is the
    thread-safe death signal (see module docstring); ``workspace_id`` is
    the chat-workspace ownership label value.
    """

    session_id: str
    relay_dir: str
    agent_argv: tuple = ()
    workspace_copy_path: str | None = None
    env_allowlist: dict = field(default_factory=dict)
    limits: dict = field(default_factory=dict)
    workspace_id: str = ""
    on_death: Callable[[str], None] | None = None


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
    """Honest-refusal placeholder (kept for tests and docker-less setups).

    ``launch`` refuses honestly (the intake pipeline persists the failed
    session and annotates the thread); ``reap_orphans`` reports no live
    sessions, so startup reconciliation fail-closes anything left over.
    """

    def launch(self, spec: SandboxSpec) -> SandboxHandle:
        raise LaunchError("no sandbox backend available")

    def reap_orphans(self, workspace_id: str) -> list[str]:
        return []


# --------------------------------------------------------------------- #
# Repo identity + workspace copy
# --------------------------------------------------------------------- #


def repo_identity(repo_root: str | Path) -> str:
    """Stable per-checkout ownership id: sha256 of the resolved root path.

    Scopes container ownership to THIS repo checkout — a logical chat
    workspace id (e.g. a Discord guild) is not unique per host-side owner.
    """
    resolved = str(Path(repo_root).resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:12]


def make_workspace_copy(repo_root: str | Path, dest: str | Path) -> Path:
    """Disposable workspace copy of committed HEAD into ``dest``.

    ``git archive HEAD | tar -x`` — committed state only: uncommitted,
    staged and untracked files never leak into the sandbox, and the copy
    carries no ``.git``. Raises :class:`LaunchError` on any failure and
    leaves no partial directory behind (launch-phase failure — callers
    share the launch fail path).
    """
    dest = Path(dest)
    try:
        dest.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        raise LaunchError(f"workspace copy dir: {exc}") from exc
    git_proc = None
    try:
        git_proc = subprocess.Popen(
            ["git", "-C", str(repo_root), "archive", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_proc = subprocess.run(
            ["tar", "-x", "-C", str(dest)],
            stdin=git_proc.stdout, stderr=subprocess.PIPE, check=False)
        git_proc.stdout.close()
        git_err = git_proc.stderr.read()
        git_rc = git_proc.wait()
        if git_rc != 0 or tar_proc.returncode != 0:
            detail = (git_err or tar_proc.stderr or b"").decode(
                "utf-8", "replace").strip()
            raise LaunchError(f"workspace copy failed: {detail}")
        return dest
    except (OSError, LaunchError):
        if git_proc is not None and git_proc.poll() is None:
            git_proc.kill()
        shutil.rmtree(dest, ignore_errors=True)
        raise
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise


def remove_workspace_copy(dest: str | Path) -> None:
    """Cleanup verb for a workspace copy (best-effort, idempotent)."""
    shutil.rmtree(Path(dest), ignore_errors=True)


# --------------------------------------------------------------------- #
# Docker backend
# --------------------------------------------------------------------- #


def build_docker_run_argv(
    spec: SandboxSpec, *, repo_id: str, image: str, deadline_epoch: int,
    uid_gid: str | None = None,
) -> list[str]:
    """Pure argv construction for ``docker run`` (test seam — needs no
    docker and no live state). Argv-list only (pinned contract 13).
    ``uid_gid`` (``"1000:1000"``) is injectable for determinism; ``None``
    resolves the current process's ids."""
    if uid_gid is None:
        uid_gid = f"{os.getuid()}:{os.getgid()}"
    limits = spec.limits
    # Basename must stay the session id — the relay lib derives/validates
    # the id from the dir name (see module docstring).
    relay_mount = f"/relay/{spec.session_id}"
    argv = [
        "docker", "run", "-d",
        "--name", f"ait-chatlink-{spec.session_id}",
        "--label", f"{LABEL_SESSION}={spec.session_id}",
        "--label", f"{LABEL_WORKSPACE}={spec.workspace_id}",
        "--label", f"{LABEL_REPO}={repo_id}",
        "--label", f"{LABEL_DEADLINE}={deadline_epoch}",
        "--user", uid_gid,
    ]
    if limits.get("memory"):
        argv += ["--memory", str(limits["memory"])]
    if limits.get("cpus"):
        argv += ["--cpus", str(limits["cpus"])]
    if limits.get("pids"):
        argv += ["--pids-limit", str(limits["pids"])]
    argv += [
        "-v", f"{spec.workspace_copy_path}:/work",
        "-v", f"{spec.relay_dir}:{relay_mount}",
        "-e", "HOME=/tmp",
        "-e", f"CHATLINK_RELAY_DIR={relay_mount}",
        "-e", f"CHATLINK_BUG_REPORT_FILE={relay_mount}/bug_report.md",
    ]
    for key, value in sorted(spec.env_allowlist.items()):
        argv += ["-e", f"{key}={value}"]
    argv += ["--workdir", "/work", image]
    argv += [str(a) for a in spec.agent_argv]
    return argv


def _run_docker(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(argv, capture_output=True, text=True, check=False)


class DockerHandle:
    """Handle over one container: liveness probe + kill + bounded wait."""

    def __init__(self, name: str, *, on_death: Callable[[str], None] | None,
                 session_id: str):
        self.name = name
        self._session_id = session_id
        self._on_death = on_death
        self._death_fired = False

    def alive(self) -> bool:
        proc = _run_docker(
            ["docker", "inspect", "-f", "{{.State.Running}}", self.name])
        if proc.returncode != 0:
            return False  # removed / unknown container
        return proc.stdout.strip() == "true"

    def wait(self, timeout: float | None = None) -> int | None:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            proc = _run_docker(
                ["docker", "inspect", "-f",
                 "{{.State.Running}} {{.State.ExitCode}}", self.name])
            if proc.returncode != 0:
                return -9  # container removed underneath us (killed)
            running, _, exit_code = proc.stdout.strip().partition(" ")
            if running != "true":
                try:
                    return int(exit_code)
                except ValueError:
                    return -9
            if deadline is not None and time.monotonic() >= deadline:
                return None
            time.sleep(0.5)

    def kill(self) -> None:
        _run_docker(["docker", "rm", "-f", self.name])  # best-effort

    def fire_death_once(self) -> None:
        """Invoke ``on_death`` at most once (watchdog-thread entry point).

        The flag is the at-most-once guard between the deadline-kill path
        and the observed-death path; a raising callback is swallowed
        (reconciliation is the backstop). Single-writer: only the one
        watchdog thread calls this, so no lock is needed.
        """
        if self._death_fired or self._on_death is None:
            return
        self._death_fired = True
        try:
            self._on_death(self._session_id)
        except Exception:
            pass


class DockerLauncher:
    """Docker backend for the seam (see module docstring for the contract).

    ``repo_id`` scopes ownership labels/filters to this checkout (pass
    ``repo_identity(<repo root>)``). ``poll_s`` is the watchdog cadence
    (injectable for tests).
    """

    def __init__(self, *, repo_id: str, image: str = DEFAULT_SANDBOX_IMAGE,
                 poll_s: float = WATCHDOG_POLL_S, clock=time.time):
        self.repo_id = repo_id
        self.image = image
        self.poll_s = poll_s
        self.clock = clock

    def launch(self, spec: SandboxSpec) -> DockerHandle:
        if shutil.which("docker") is None:
            raise LaunchError(
                "docker not found — install Docker or disable the sandbox "
                "feature (see aidocs/chat/chatlink_sandbox.md)")
        if spec.workspace_copy_path is None:
            raise LaunchError(
                "workspace_copy_path is required by the docker backend "
                "(disposable copy of committed HEAD — never a live mount)")
        wall_clock_s = int(spec.limits.get("wall_clock_s") or 0)
        deadline_epoch = int(self.clock()) + wall_clock_s
        argv = build_docker_run_argv(
            spec, repo_id=self.repo_id, image=self.image,
            deadline_epoch=deadline_epoch)
        proc = _run_docker(argv)
        if proc.returncode != 0:
            raise LaunchError(
                f"docker run failed: {proc.stderr.strip() or proc.stdout.strip()}")
        handle = DockerHandle(f"ait-chatlink-{spec.session_id}",
                              on_death=spec.on_death,
                              session_id=spec.session_id)
        self._start_watchdog(handle, deadline_epoch)
        return handle

    def _start_watchdog(self, handle: DockerHandle,
                        deadline_epoch: int) -> None:
        """Per-launch supervisor: wall-clock kill + death signalling.

        Runs as a daemon thread; performs docker probes and the at-most-once
        ``on_death`` signal ONLY — no spool/store I/O and no asyncio calls
        (the chatlink callback marshals onto the loop itself). If the
        gateway dies with the thread, the deadline label lets a restarted
        gateway's ``reap_orphans`` finish the job statelessly.
        """

        def watch() -> None:
            while True:
                if not handle.alive():
                    handle.fire_death_once()
                    return
                if self.clock() >= deadline_epoch:
                    handle.kill()
                    handle.fire_death_once()
                    return
                time.sleep(self.poll_s)

        threading.Thread(target=watch, daemon=True,
                         name=f"sandbox-watchdog-{handle.name}").start()

    def reap_orphans(self, workspace_id: str) -> list[str]:
        """Stateless orphan pass (see module docstring's reap semantics).

        Raises on docker failure — the daemon already treats a reap failure
        as "assume none live" (fail-closed).
        """
        proc = _run_docker([
            "docker", "ps", "-a",
            "--filter", f"label={LABEL_WORKSPACE}={workspace_id}",
            "--filter", f"label={LABEL_REPO}={self.repo_id}",
            "--format",
            ("{{.ID}}\t{{.State}}"
             f"\t{{{{.Label \"{LABEL_SESSION}\"}}}}"
             f"\t{{{{.Label \"{LABEL_DEADLINE}\"}}}}"),
        ])
        if proc.returncode != 0:
            raise LaunchError(f"docker ps failed: {proc.stderr.strip()}")

        def rm(argv: list[str]) -> None:
            # A failed removal must RAISE (never silently drop the session
            # from the live set — the container may still be running with
            # a stale bind mount while reconciliation removes its state).
            rm_proc = _run_docker(argv)
            if rm_proc.returncode != 0:
                raise LaunchError(
                    f"docker {' '.join(argv[1:])} failed: "
                    f"{rm_proc.stderr.strip()}")

        live: list[str] = []
        now = self.clock()
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 4:
                continue
            cid, state, session_id, deadline_raw = parts
            if state != "running":
                rm(["docker", "rm", cid])
                continue
            try:
                deadline = int(deadline_raw)
            except ValueError:
                deadline = 0  # malformed deadline: fail-closed — reap it
            if now >= deadline:
                rm(["docker", "rm", "-f", cid])
                continue
            live.append(session_id)
        return sorted(live)


# --------------------------------------------------------------------- #
# Backend registry (mirrors lib/launch_modes.py + agentcrew LAUNCHERS)
# --------------------------------------------------------------------- #

BACKENDS: dict[str, type] = {
    "docker": DockerLauncher,
}

assert set(BACKENDS.keys()) == set(VALID_SANDBOX_BACKENDS), (
    "BACKENDS registry out of sync with VALID_SANDBOX_BACKENDS: "
    f"missing={set(VALID_SANDBOX_BACKENDS) - set(BACKENDS.keys())}, "
    f"extra={set(BACKENDS.keys()) - set(VALID_SANDBOX_BACKENDS)}"
)


def get_launcher(backend: str, **kwargs) -> Launcher:
    """Construct the registered backend (``kwargs`` are backend-specific,
    e.g. ``repo_id=`` for docker)."""
    cls = BACKENDS.get(backend)
    if cls is None:
        raise LaunchError(
            f"unknown sandbox backend '{backend}' "
            f"(valid: {', '.join(sorted(VALID_SANDBOX_BACKENDS))})")
    return cls(**kwargs)


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
