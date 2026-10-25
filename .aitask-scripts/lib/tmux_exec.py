"""tmux_exec - The single Python gateway for spawning ``tmux`` processes.

`TmuxClient` is intended to become the **only** place in the Python side of the
framework that launches a raw ``tmux`` process. It owns four cross-cutting
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
   ``monitor/``. Pane-creating verbs never ride the control client (policy 4).

4. **Pane PATH (t1689).** tmux gives a new pane the PATH of the *client process
   that issued* ``new-window`` / ``split-window`` / ``new-session`` — it even
   overrides ``-e PATH=…`` — so the pane's PATH order depends on whoever
   spawned it. An *attached* control client donates nothing: its spawns get the
   server's global PATH, frozen at server start. Every tmux client launched
   here therefore carries :func:`normalize_spawn_path` of the caller's PATH
   (``env=`` only when that changes anything), pane-creating commands bypass
   the control client (:func:`creates_pane`), and the systemd-run rung of
   :meth:`TmuxClient.new_session_argv` hands the new server the same PATH via
   ``--setenv``. Reordering is for the *pane* only: the launcher binaries
   (``tmux``, ``setsid``, ``systemd-run``) stay the ones the caller's PATH
   resolves (:func:`resolve_spawn_exe`). Shell mirror: ``lib/spawn_path.sh``.

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
import functools
import os
import re
import shutil
import subprocess
from typing import NamedTuple

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


# tmux verbs whose new pane inherits the issuing client's PATH (policy 4). Full
# spellings only: the framework never uses tmux's aliases (`neww`, `splitw`).
_PANE_CREATING_VERBS = frozenset({
    "new-session", "new-window", "split-window",
    "respawn-pane", "respawn-window",
})


def creates_pane(args: list[str]) -> bool:
    """Whether a tmux argv creates (or respawns) a pane.

    Any token counts, so a ``\\;``-chained command that creates a pane anywhere
    is caught. A false positive only costs a subprocess instead of the control
    client, so matching on bare tokens errs on the safe side.
    """
    return any(a in _PANE_CREATING_VERBS for a in args)


def _strip_entry(entry: str) -> str:
    """A PATH entry without trailing slashes, keeping a lone ``/``."""
    stripped = entry.rstrip("/")
    return stripped or ("/" if entry.startswith("/") else entry)


@functools.lru_cache(maxsize=32)
def _normalize_cached(path: str, home: str, mise_data_dir: str,
                      xdg_data_home: str, aitasks_home: str) -> str:
    if mise_data_dir:
        data = mise_data_dir.rstrip("/")
    elif xdg_data_home:
        data = xdg_data_home.rstrip("/") + "/mise"
    elif home:
        data = home.rstrip("/") + "/.local/share/mise"
    else:
        return path
    shims = data + "/shims"
    installs = data + "/installs/"

    framework = set()
    if home:
        framework.add(home.rstrip("/") + "/.aitask/bin")
    if aitasks_home:
        framework.add(aitasks_home.rstrip("/") + "/bin")
    elif home:
        framework.add(home.rstrip("/") + "/.aitasks/bin")

    lead: list[str] = []
    mise: list[str] = []
    rest: list[str] = []
    leading = True
    for entry in path.split(":"):
        norm = _strip_entry(entry)
        if norm == shims or norm.startswith(installs):
            mise.append(entry)
        elif leading and norm and norm in framework:
            lead.append(entry)
        else:
            leading = False
            rest.append(entry)
    if not mise:
        return path
    return ":".join(lead + mise + rest)


def _which(name: str, path: str, cwd=None) -> str | None:
    """First executable ``name`` on ``path`` (an empty entry means ``.``).

    A deliberate mirror of ``lib/spawn_path.sh::_ait_spawn_path_which`` rather
    than :func:`shutil.which`, so the two gateways agree on every PATH.

    ``cwd`` is the directory the child will run in. ``subprocess`` searches PATH
    in the child *after* changing into it, so a relative entry (``bin``, or the
    empty one) names a directory under ``cwd``, not under ours; such a match is
    returned as an ABSOLUTE path under ``cwd``. ``cwd`` itself may be relative
    (to our directory — where the child's chdir starts from), and a relative pin
    would be re-resolved from inside it after that chdir, naming nothing.

    The base is made absolute by concatenation only — never ``abspath`` /
    ``normpath``. Those collapse ``..`` lexically, while the kernel resolves it
    after following symlinks: with ``link -> elsewhere/nested``, ``link/..`` is
    ``elsewhere``, not our directory. Left in place, the kernel reads the pinned
    path exactly as it reads the child's ``chdir(cwd)``.
    """
    base = None
    if cwd is not None:
        base = os.fsdecode(cwd)
        if not base.startswith("/"):
            base = os.getcwd() + "/" + base
    for entry in path.split(":"):
        # Plain concatenation (not os.path.join) so a trailing-slash entry
        # yields the same string the shell mirror builds.
        candidate = (entry or ".") + "/" + name
        if base is not None and not candidate.startswith("/"):
            candidate = base + "/" + candidate
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def resolve_spawn_exe(name: str, original_path: str | None,
                      spawn_path: str, cwd=None) -> str:
    """``name`` spelled so a process running under ``spawn_path`` executes the
    file the caller's own ``original_path`` resolves.

    Reordering PATH for the pane must not change *which launcher* runs: a
    working ``tmux`` ahead of a mise-managed one that fails in this project
    would otherwise be swapped out. Returns the bare ``name`` when both PATHs
    resolve the same file (or the caller's resolves none, so the launch fails
    exactly as before), and the caller's path to it only when they differ.
    ``cwd`` is the child's working directory, as passed to ``Popen`` (see
    :func:`_which`); ``None`` means it inherits ours.
    """
    if original_path is None or original_path == spawn_path:
        return name
    original = _which(name, original_path, cwd)
    if original is None or _which(name, spawn_path, cwd) == original:
        return name
    return original


def normalize_spawn_path(path: str, environ=None) -> str:
    """The PATH a framework-spawned tmux client (and so its pane) should carry.

    When ``path`` holds a mise entry — ``<mise_data>/shims`` or anything under
    ``<mise_data>/installs/``, with ``mise_data`` = ``$MISE_DATA_DIR`` or
    ``${XDG_DATA_HOME:-$HOME/.local/share}/mise`` — reorder it to: the framework
    bins (``$HOME/.aitask/bin``, ``${AITASKS_HOME:-$HOME/.aitasks}/bin``) that
    lead it, then every mise entry, then everything else. Relative order is kept
    within each group, empty entries survive, entries compare with trailing
    slashes stripped. No mise entry → ``path`` unchanged. Idempotent.

    That is the order a mise-activated interactive shell already has. Under the
    opposite order, with no ``__MISE_*`` session vars (tmux drops them), a
    ``mise x <agent> -- <agent>`` wrapper in ``~/.local/bin`` resolves back to
    itself and ``exec``s forever: a blank agent pane (t1689). Shell mirror:
    ``lib/spawn_path.sh::ait_spawn_path_normalize``.
    """
    env = os.environ if environ is None else environ
    return _normalize_cached(
        path,
        env.get("HOME") or "",
        env.get("MISE_DATA_DIR") or "",
        env.get("XDG_DATA_HOME") or "",
        env.get("AITASKS_HOME") or "",
    )


def session_target(session: str) -> str:
    """Return an exact-match tmux ``-t`` session target (``=<session>``).

    tmux resolves ``-t <name>`` as a prefix match by default, so ``-t aitasks``
    matches ``aitasks_mob`` when only the latter is running. The ``=`` prefix
    forces exact match and is mandatory whenever aitasks projects with
    prefix-sharing session names run side by side. (Promoted here from the
    "available" helper in ``agent_launch_utils.tmux_session_target``.)

    Only for SESSION-typed ``-t`` (``has-session``, ``list-windows``,
    ``set-environment``, …). A window- or pane-typed ``-t`` that must address a
    whole session — notably ``list-panes -s`` — takes
    :func:`session_scope_target`.
    """
    return f"={session}"


def session_scope_target(session: str) -> str:
    """Return ``=<session>:`` — a whole-session target for a WINDOW-typed ``-t``.

    ``list-panes`` resolves ``-t`` as a window and ``-s`` then widens to that
    window's session. A bare ``=<session>`` is looked up as a window NAME
    first, in the current session (or, with no client, the most recently used
    one): when that session has a window called ``<session>`` — which
    ``automatic-rename-format '#{b:pane_current_path}'`` produces from any pane
    whose cwd basename matches — tmux lists that OTHER session's panes
    (measured on tmux 3.7c, t1874). The trailing colon makes the session part
    explicit, so it cannot match a window.
    """
    return f"={session}:"


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


class TmuxResult(NamedTuple):
    """Outcome of :meth:`TmuxClient.run_checked` — a status-bearing tmux call.

    ``outcome`` is one of:

    * ``ok``        — rc 0.
    * ``no_tmux``   — the ``tmux`` binary is not installed. No server can exist.
    * ``no_server`` — tmux answered that no server listens on the socket. A
      definite "nothing is running", NOT a failure.
    * ``failed``    — anything else: a timeout, an ``OSError``, or a non-zero
      exit this table does not recognize. Callers that must rule something out
      treat this as "could not look" and fail closed.

    A command-specific non-zero answer that is nonetheless definite ("unknown
    variable", "can't find session") comes back as ``failed`` with its
    ``stderr``: the gateway does not know which command's miss is benign, so the
    caller classifies it with :func:`tmux_stderr_is` against the pinned table.
    """

    outcome: str
    rc: int
    stdout: str
    stderr: str


#: tmux's own error messages, measured against tmux 3.7c (t1869) — never
#: guessed. A missing socket file prints ``error connecting to <path> (No such
#: file or directory)``; a socket file with no listener (a server that died)
#: prints ``no server running on <path>``. Both mean "no server". A vanished
#: session prints ``can't find session: <s>`` for an ``=<s>:`` target and
#: ``can't find window: <s>`` for a bare ``=<s>`` one; an unset global
#: environment variable prints ``unknown variable: <v>``. Anything else — e.g.
#: ``(Connection refused)`` or ``(Permission denied)`` — is not in this table
#: and therefore stays a failure.
_TMUX_STDERR_PATTERNS = {
    "no_server": (
        re.compile(r"^no server running on "),
        re.compile(r"^error connecting to .* \(No such file or directory\)$"),
    ),
    "no_such_session": (
        re.compile(r"^can't find session: "),
        re.compile(r"^can't find window: "),
    ),
    "unknown_variable": (re.compile(r"^unknown variable: "),),
}


def tmux_stderr_is(kind: str, stderr: str) -> bool:
    """True if ``stderr``'s first line matches the pinned ``kind`` pattern."""
    first = (stderr or "").strip().splitlines()[:1]
    if not first:
        return False
    return any(p.search(first[0]) for p in _TMUX_STDERR_PATTERNS[kind])


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

    @staticmethod
    def spawn_env(base=None) -> dict | None:
        """The environment a tmux client process should get (policy 4).

        ``base`` (default ``os.environ``) with ``PATH`` replaced by
        :func:`normalize_spawn_path`, or ``None`` when that changes nothing —
        meaning "inherit", so hosts without mise see exactly today's calls.
        """
        src = os.environ if base is None else base
        path = src.get("PATH")
        if path is None:
            return None
        normalized = normalize_spawn_path(path, src)
        if normalized == path:
            return None
        env = dict(src)
        env["PATH"] = normalized
        return env

    def _launch(self, args: list[str], base=None,
                cwd=None) -> tuple[list[str], dict]:
        """The argv and extra subprocess kwargs for one tmux client (policy 4).

        ``({argv}, {})`` — inherit — when normalization changes nothing.
        Otherwise ``{"env": …}`` with the normalized PATH, and ``tmux`` spelled
        so it is still the binary the caller's own PATH resolves
        (:func:`resolve_spawn_exe`) from the child's working directory ``cwd``.
        """
        src = os.environ if base is None else base
        argv = self._argv(args)
        env = self.spawn_env(src)
        if env is None:
            return argv, {}
        argv[0] = resolve_spawn_exe("tmux", src.get("PATH"), env["PATH"], cwd)
        return argv, {"env": env}

    def run(
        self, args: list[str], timeout: float = _DEFAULT_TIMEOUT
    ) -> tuple[int, str]:
        """Run ``tmux <args>`` synchronously. Returns ``(returncode, stdout)``.

        ``(-1, "")`` on ``FileNotFoundError`` / ``OSError`` / timeout. This is the
        canonical subprocess primitive — the control-mode dispatcher
        (:meth:`run_via_control`) falls back to it on a transport failure.
        """
        argv, extra = self._launch(args)
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout, **extra,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return (-1, "")
        return (result.returncode, result.stdout or "")

    def run_checked(
        self, args: list[str], timeout: float = _DEFAULT_TIMEOUT
    ) -> TmuxResult:
        """Run ``tmux <args>`` and say *why* it failed, not just that it did.

        :meth:`run` folds every failure into ``(-1, "")`` or a bare non-zero rc
        and drops stderr, so "no server is running" and "the query failed" are
        indistinguishable there. That is fine for display loops; it is wrong for
        a caller that must *rule out* a live session before acting (the
        cross-repo note resolver, t1869). This additive sibling keeps stderr
        and classifies the outcome — see :class:`TmuxResult`.
        """
        argv, extra = self._launch(args)
        try:
            result = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout, **extra,
            )
        except FileNotFoundError:
            return TmuxResult("no_tmux", -1, "", "")
        except (subprocess.TimeoutExpired, OSError):
            return TmuxResult("failed", -1, "", "")
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        if result.returncode == 0:
            return TmuxResult("ok", 0, stdout, stderr)
        if tmux_stderr_is("no_server", stderr):
            return TmuxResult("no_server", result.returncode, stdout, stderr)
        return TmuxResult("failed", result.returncode, stdout, stderr)

    def set_clipboard(self, text: str, timeout: float = _DEFAULT_TIMEOUT) -> bool:
        """Push ``text`` to the system clipboard through the tmux server.

        ``load-buffer -w -`` (text on stdin) sets a tmux paste buffer AND
        forwards it to every attached client's terminal via OSC 52. This is the
        only clipboard path that works from a **non-visible** pane: a plain
        OSC 52 written by an application in a hidden window is stored as a tmux
        buffer but never forwarded to the outer terminal, so the system
        clipboard is silently left untouched. Returns ``True`` on success;
        ``False`` on any failure (no tmux, tmux < 3.2 lacking ``-w``, timeout).
        """
        argv, extra = self._launch(["load-buffer", "-w", "-"])
        try:
            result = subprocess.run(
                argv, input=text, capture_output=True, text=True,
                timeout=timeout, **extra,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
        return result.returncode == 0

    async def run_async(
        self, args: list[str], timeout: float = _DEFAULT_TIMEOUT
    ) -> tuple[int, str]:
        """Async sibling of :meth:`run`. Same ``(rc, stdout)`` contract.

        ``(-1, "")`` on ``FileNotFoundError`` / ``OSError`` / timeout. On timeout
        the child is killed and reaped before returning. The async fallback for
        :meth:`run_async_via_control`.
        """
        argv, extra = self._launch(args)
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                **extra,
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

        A caller-supplied ``env`` gets its ``PATH`` normalized like the
        inherited one (policy 4).
        """
        argv, extra = self._launch(args, popen_kwargs.get("env"),
                                   popen_kwargs.get("cwd"))
        popen_kwargs.update(extra)
        return subprocess.Popen(argv, **popen_kwargs)

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

        Pane-creating commands skip the backend: a pane spawned through an
        attached control client gets the server's global PATH (frozen at server
        start), not a normalized one — only a fresh client donates its PATH
        (policy 4, measured on tmux 3.6a in t1689).
        """
        if creates_pane(args):
            return self.run(args, timeout=timeout)
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
        :meth:`run_async` on ``rc == -1`` from the backend. Pane-creating
        commands skip the backend, as in :meth:`run_via_control`.
        """
        if creates_pane(args):
            return await self.run_async(args, timeout=timeout)
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
    def session_scope_target(session: str) -> str:
        return session_scope_target(session)

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
        prefix = [
            "systemd-run", "--user", "--slice=session.slice", f"--unit={unit}",
            "--property=Type=forking", "--property=KillMode=none",
            "--collect", "--quiet",
        ]
        # The unit runs in the user manager's environment, not ours, so its
        # PATH would otherwise become the new server's global PATH. Hand it the
        # same normalized PATH the setsid / plain rungs pass by inheritance.
        path = os.environ.get("PATH")
        if path is not None:
            prefix.append(f"--setenv=PATH={normalize_spawn_path(path)}")
        return prefix + ["--"]

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
        returned argv is meant to be passed straight to ``subprocess.Popen``
        **with** ``env=client.spawn_env()`` — the setsid / plain rungs hand the
        new pane the launching process's PATH (policy 4).
        """
        cwd_args = cwd_args or []
        # The caller Popens this with env=spawn_env(): every launcher token is
        # spelled so that normalized PATH still runs the binary OURS resolves.
        env = self.spawn_env()

        def exe(name: str) -> str:
            if env is None:
                return name
            return resolve_spawn_exe(name, os.environ.get("PATH"), env["PATH"])

        base = [exe("tmux"), *self._socket_args, "new-session", "-d",
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
            return [exe(prefix[0]), *prefix[1:]] + created
        if shutil.which("setsid"):
            return [exe("setsid")] + created
        return created
