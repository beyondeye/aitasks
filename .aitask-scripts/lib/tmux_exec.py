"""tmux_exec - The single Python gateway for spawning ``tmux`` processes.

`TmuxClient` is intended to become the **only** place in the Python side of the
framework that launches a raw ``tmux`` process. It owns three cross-cutting
policies that are currently implicit and duplicated across call sites (t952):

1. **Socket selection.** The framework runs its tmux sessions on a dedicated
   named socket (``-L ait``, t953) so the ait backend is isolated from the
   user's personal default server. The gateway centralizes this in one place —
   see :func:`tmux_socket_args`. It reads the env var ``AITASKS_TMUX_SOCKET``
   once at client construction (never per-call: the monitor fallback path is a
   hot path). Unset → ``-L ait`` (the dedicated default); ``default`` → the
   user's default server (explicit opt-out); set-but-empty → no flag (legacy
   escape hatch that follows ``$TMUX``, used by the test isolation harness).
   The shell mirror (``lib/tmux_exec.sh``, t952_4) and the control-mode attach
   (t952_3) read the same var so all clients converge on one value.

2. **Target formatting.** :func:`session_target` / :func:`window_target` (the
   ``=<session>`` exact-match helpers, promoted here from "available" to
   "mandatory") so callers cannot hand-format ``-t`` and reintroduce the tmux
   prefix-match bug that crosses project boundaries.

3. **Exec strategy.** The per-tick subprocess primitives live here
   (:meth:`TmuxClient.run` / :meth:`run_async` / :meth:`spawn`), and so does the
   control-mode dispatch (:meth:`run_via_control` / :meth:`run_async_via_control`):
   "persistent control client when alive, subprocess fallback on ``rc == -1``".
   The control client itself (``monitor/tmux_control.py``) is passed in
   duck-typed, so the gateway owns the *strategy* without depending on
   ``monitor/``.

The spawn primitives (:meth:`TmuxClient.run` / :meth:`run_async`) are the sole
owner of the ``(rc, stdout)`` contract — ``(-1, "")`` on ``FileNotFoundError`` /
``OSError`` / timeout — and serve as the subprocess fallback for the control-mode
dispatcher (:meth:`run_via_control` / :meth:`run_async_via_control`, t952_3). The
new-session persistence ladder mirrors ``agent_launch_utils`` /
``terminal_compat.sh`` byte-for-byte (load-bearing for t943/t956 server
survival).

Usage::

    from tmux_exec import TmuxClient
    client = TmuxClient()
    rc, out = client.run(["list-sessions", "-F", "#{session_name}"])
    argv = client.new_session_argv("aitasks", "monitor", "ait monitor")
    subprocess.Popen(argv)
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import subprocess

# Env var naming the tmux socket (``tmux -L <name>``). Unset → the dedicated
# ``ait`` socket (t953); ``default`` → the user's default server (opt-out);
# set-but-empty → no flag (legacy escape hatch, follows ``$TMUX``). Shared
# verbatim with the shell gateway ``lib/tmux_exec.sh``.
TMUX_SOCKET_ENV = "AITASKS_TMUX_SOCKET"

# The dedicated socket name every ait-managed tmux session lives on when the
# env var is unset (t953). ONE shared server for all aitasks projects —
# sessions stay per-project, so the multi-session `j` switcher keeps working.
# Mirrored verbatim in ``lib/tmux_exec.sh`` (AIT_DEDICATED_SOCKET).
AIT_DEDICATED_SOCKET = "ait"

_DEFAULT_TIMEOUT = 5.0


def tmux_socket_args() -> list[str]:
    """Return the socket flag for every ``tmux`` invocation, from one source.

    Reads ``AITASKS_TMUX_SOCKET`` (t953 semantics):

    * **unset** → ``["-L", "ait"]`` — the dedicated ait socket (default).
    * **non-empty** → ``["-L", value]`` — a named socket on the standard
      ``$TMUX_TMPDIR``. ``AITASKS_TMUX_SOCKET=default`` is the explicit opt-out:
      tmux's default socket is literally named ``default``.
    * **set but empty/whitespace** → ``[]`` — legacy escape hatch: no flag, so
      tmux follows ``$TMUX`` ambient resolution. Used by the test isolation
      harness (``tests/lib/tmux_isolation.sh``).

    ``-L`` (socket name) rather than ``-S`` (socket path) is chosen so the value
    composes with tmux's standard tmpdir resolution and with the test isolation
    harness (``TMUX_TMPDIR`` redirection).
    """
    raw = os.environ.get(TMUX_SOCKET_ENV)
    if raw is None:
        return ["-L", AIT_DEDICATED_SOCKET]
    sock = raw.strip()
    return ["-L", sock] if sock else []


def session_target(session: str) -> str:
    """Return an exact-match tmux ``-t`` session target (``=<session>``).

    tmux resolves ``-t <name>`` as a prefix match by default, so ``-t aitasks``
    matches ``aitasks_mob`` when only the latter is running. The ``=`` prefix
    forces exact match and is mandatory whenever aitasks projects with
    prefix-sharing session names run side by side. (Promoted here from the
    "available" helper in ``agent_launch_utils.tmux_session_target``.)
    """
    return f"={session}"


def window_target(session: str, window: str | int) -> str:
    """Return an exact-match tmux ``-t`` ``session:window`` target.

    Only the session part is anchored with ``=`` (window names/indices do not
    suffer tmux's session-level prefix match). Pass ``window=""`` for the
    "trailing colon" idiom ``new-window`` uses to mean "create in this session".
    """
    return f"={session}:{window}"


def _systemd_user_available() -> bool:
    """Whether a usable ``systemd --user`` manager is reachable for systemd-run.

    Python mirror of ``ait_systemd_user_available`` in ``terminal_compat.sh``
    (t943). Honors the ``AIT_NO_SYSTEMD_RUN`` test/escape hatch and accepts a
    ``running`` or ``degraded`` user manager.
    """
    if os.environ.get("AIT_NO_SYSTEMD_RUN"):
        return False
    if shutil.which("systemd-run") is None or shutil.which("systemctl") is None:
        return False
    if not os.environ.get("XDG_RUNTIME_DIR"):
        return False
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-system-running"],
            capture_output=True, text=True, timeout=_DEFAULT_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    return result.returncode == 0 or result.stdout.strip() == "degraded"


class TmuxClient:
    """Sole owner of raw ``tmux`` process spawning on the Python side.

    All methods take tmux args **without** the leading ``"tmux"`` (e.g.
    ``client.run(["list-sessions"])``); the client prepends ``tmux`` and the
    cached socket args. Socket args are resolved **once** at construction so the
    hot path never re-reads the environment.
    """

    def __init__(self, socket_args: list[str] | None = None):
        # Cached once — never recomputed per call (monitor fallback hot path).
        self._socket_args = (
            list(socket_args) if socket_args is not None else tmux_socket_args()
        )

    @property
    def socket_args(self) -> list[str]:
        """The cached socket flag prepended to every invocation (read-only copy)."""
        return list(self._socket_args)

    def _argv(self, args: list[str]) -> list[str]:
        """Build the full process argv: ``tmux`` + socket flag + caller args."""
        return ["tmux", *self._socket_args, *args]

    def run(
        self, args: list[str], timeout: float = _DEFAULT_TIMEOUT
    ) -> tuple[int, str]:
        """Run ``tmux <args>`` synchronously. Returns ``(returncode, stdout)``.

        ``(-1, "")`` on ``FileNotFoundError`` / ``OSError`` / timeout. This is the
        canonical subprocess primitive — the control-mode dispatcher
        (:meth:`run_via_control`) falls back to it on a transport failure.
        """
        try:
            result = subprocess.run(
                self._argv(args),
                capture_output=True, text=True, timeout=timeout,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return (-1, "")
        return (result.returncode, result.stdout or "")

    async def run_async(
        self, args: list[str], timeout: float = _DEFAULT_TIMEOUT
    ) -> tuple[int, str]:
        """Async sibling of :meth:`run`. Same ``(rc, stdout)`` contract.

        ``(-1, "")`` on ``FileNotFoundError`` / ``OSError`` / timeout. On timeout
        the child is killed and reaped before returning. The async fallback for
        :meth:`run_async_via_control`.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._argv(args),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except (FileNotFoundError, OSError):
            return (-1, "")
        try:
            stdout_bytes, _ = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()
            return (-1, "")
        return (proc.returncode or 0, stdout_bytes.decode("utf-8", errors="replace"))

    def spawn(self, args: list[str], **popen_kwargs) -> subprocess.Popen:
        """Fire-and-forget spawn of ``tmux <args>``. Returns the ``Popen``.

        For sites that do not capture output and do not block (UI updates like
        ``switch-client`` / ``select-window``, or ``new-session`` argvs the
        caller manages). Unlike :meth:`run`/:meth:`run_async` this does not
        swallow ``FileNotFoundError`` — a fire-and-forget caller that needs the
        no-tmux case handled should guard with ``shutil.which("tmux")`` (as the
        current call sites already do via ``is_tmux_available``).
        """
        return subprocess.Popen(self._argv(args), **popen_kwargs)

    # -- control-mode exec dispatcher ---------------------------------------
    # "Control-client when alive, subprocess fallback on rc == -1." This is the
    # exec-strategy choice the gateway owns (t952_3): the persistent control
    # client (a `tmux -C attach` connection, see monitor/tmux_control.py) when it
    # is alive, otherwise a per-tick subprocess via run/run_async. The backend is
    # passed in (duck-typed) rather than held, so the gateway stays stateless
    # w.r.t. the channel and the backend lifecycle stays with its owner.

    def run_via_control(
        self, backend, args: list[str], timeout: float = _DEFAULT_TIMEOUT
    ) -> tuple[int, str]:
        """Sync exec dispatch: control client when alive, else subprocess.

        ``backend`` is a control-mode backend (duck-typed: ``.is_alive`` /
        ``.request_sync``) or ``None``. On a transport failure (``rc == -1``)
        from the backend, falls back to :meth:`run`. Behavior-preserving port of
        the former ``TmuxMonitor.tmux_run`` dispatch — the ``rc != -1`` fallback
        branch is load-bearing.
        """
        if backend is not None and backend.is_alive:
            rc, out = backend.request_sync(args, timeout=timeout)
            if rc != -1:
                return rc, out
        return self.run(args, timeout=timeout)

    async def run_async_via_control(
        self, backend, args: list[str], timeout: float = _DEFAULT_TIMEOUT
    ) -> tuple[int, str]:
        """Async sibling of :meth:`run_via_control`.

        Port of the former ``TmuxMonitor._tmux_async`` dispatch. Falls back to
        :meth:`run_async` on ``rc == -1`` from the backend.
        """
        if backend is not None and backend.is_alive:
            rc, out = await backend.request_async(args, timeout=timeout)
            if rc != -1:
                return rc, out
        return await self.run_async(args, timeout=timeout)

    # -- pane geometry ------------------------------------------------------

    def resize_pane(
        self, pane: str, *, x: int | None = None, y: int | None = None,
        backend=None, timeout: float = _DEFAULT_TIMEOUT,
    ) -> tuple[int, str]:
        """Resize ``pane`` to ``x`` columns and/or ``y`` rows.

        Sole owner of the ``resize-pane`` verb. When ``backend`` is supplied it
        dispatches through the control client if alive (same exec strategy as
        :meth:`run_via_control`), else a direct subprocess via :meth:`run`.
        """
        args = ["resize-pane", "-t", pane]
        if x is not None:
            args += ["-x", str(x)]
        if y is not None:
            args += ["-y", str(y)]
        if backend is not None:
            return self.run_via_control(backend, args, timeout=timeout)
        return self.run(args, timeout=timeout)

    # -- session/window targeting (mandatory; thin instance-level re-exports) --

    @staticmethod
    def session_target(session: str) -> str:
        return session_target(session)

    @staticmethod
    def window_target(session: str, window: str | int) -> str:
        return window_target(session, window)

    # -- new-session persistence argv builder -------------------------------

    def _server_running(self) -> bool:
        """Whether a tmux server is already up on this client's socket.

        Probes via the gateway itself so the existence check and the subsequent
        ``new-session`` share one socket (no split-brain). ``tmux list-sessions``
        exits non-zero with no server, which :meth:`run` maps to ``(1, "")`` /
        ``(-1, "")`` — either way an empty session list.
        """
        rc, out = self.run(["list-sessions", "-F", "#{session_name}"])
        return rc == 0 and any(line for line in out.splitlines())

    def _persistent_new_session_prefix(self, session: str) -> list[str] | None:
        """systemd-run argv prefix landing a new tmux SERVER in a persistent
        ``session.slice`` service, or ``None`` when ``systemd --user`` is
        unavailable.

        Python mirror of the systemd-run rung of
        ``ait_tmux_new_session_persistent`` (t943): the new server escapes the
        transient ``app.slice`` scope so a compositor / ``app.slice`` teardown
        can no longer reap it (t956). The returned prefix is concatenated with a
        ``tmux … new-session -d …`` argv.
        """
        if not _systemd_user_available():
            return None
        safe = "session"
        try:
            esc = subprocess.run(
                ["systemd-escape", "--", session],
                capture_output=True, text=True, timeout=_DEFAULT_TIMEOUT,
            )
            if esc.returncode == 0 and esc.stdout.strip():
                safe = esc.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass
        # --slice=session.slice is the load-bearing flag (escapes app.slice).
        # Type=forking matches tmux's double-fork; KillMode=none keeps systemd
        # from signalling the server cgroup when the launching transaction
        # finishes; --collect GCs the unit in the benign loser-of-a-race case.
        unit = f"ait-tmux-{safe}-{os.getpid()}-{os.urandom(3).hex()}"
        return [
            "systemd-run", "--user", "--slice=session.slice", f"--unit={unit}",
            "--property=Type=forking", "--property=KillMode=none",
            "--collect", "--quiet", "--",
        ]

    def new_session_argv(
        self,
        session: str,
        window: str,
        command: str,
        cwd_args: list[str] | None = None,
        cwd: str | None = None,
    ) -> list[str]:
        """Build the argv that creates a detached tmux session, socket-aware.

        When this call genuinely creates the tmux SERVER (no server running yet),
        it is wrapped in a persistent ``session.slice`` systemd-user service so a
        compositor / ``app.slice`` teardown can't reap it (t956, mirroring t943's
        ``ait_tmux_new_session_persistent``), with a setsid → plain-tmux fallback
        ladder. When a server is already running this is an *attach*, not a
        server creation, so the plain invocation is used unchanged. The cached
        socket flag is injected into the ``tmux`` portion in all rungs.

        Faithful port of ``agent_launch_utils._new_session_tmux_argv``; the
        returned argv is meant to be passed straight to ``subprocess.Popen``.
        """
        cwd_args = cwd_args or []
        base = ["tmux", *self._socket_args, "new-session", "-d",
                "-s", session, "-n", window]
        if self._server_running():
            # Server already running → new-session attaches a session (no server
            # creation). Preserve today's default-cwd behavior — no forced -c
            # when cwd is None.
            return base + cwd_args + [command]
        # No server running → this new-session creates it. The systemd-run /
        # setsid rungs sever the launcher relationship, so pass an explicit -c:
        # once detached, the default "inherit the launcher's cwd" no longer
        # holds, and ``cwd or os.getcwd()`` reproduces today's inherited cwd.
        created = base + ["-c", cwd or os.getcwd(), command]
        prefix = self._persistent_new_session_prefix(session)
        if prefix is not None:
            return prefix + created
        if shutil.which("setsid"):
            return ["setsid"] + created
        return created
