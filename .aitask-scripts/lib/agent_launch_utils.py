"""agent_launch_utils - Shared utilities for launching code agents from TUI screens.

Non-UI module (no Textual dependency). Provides terminal detection, agent command
resolution, and tmux session/window management.

Usage:
    from agent_launch_utils import (
        find_terminal, resolve_dry_run_command, resolve_agent_string,
        is_tmux_available, get_tmux_sessions, get_tmux_windows,
        launch_in_tmux, load_tmux_defaults, TmuxLaunchConfig,
        AitasksSession, discover_aitasks_sessions, switch_to_pane_anywhere,
    )
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tui_registry import TUI_NAMES as _DEFAULT_TUI_NAMES

# Known git management TUIs in preference order
KNOWN_GIT_TUIS = ["lazygit", "gitui", "tig"]


def tmux_session_target(session: str) -> str:
    """Return an exact-match tmux ``-t`` session target (``=<session>``).

    tmux resolves ``-t <name>`` as a prefix match by default, so ``-t aitasks``
    will match ``aitasks_mob`` when only the latter is running. Prefixing the
    name with ``=`` forces exact match and is required whenever multiple
    aitasks projects run side-by-side with session names sharing a prefix.
    """
    return f"={session}"


def tmux_window_target(session: str, window: str | int) -> str:
    """Return an exact-match tmux ``-t`` session:window target.

    Only the session part is anchored with ``=``; window names and indices
    do not suffer tmux's session-level prefix match. Pass ``window=""`` for
    the "trailing colon" idiom used by ``new-window`` to mean "create in this
    session".
    """
    return f"={session}:{window}"


def detect_git_tuis() -> list[str]:
    """Return list of installed git TUI tool names."""
    return [tool for tool in KNOWN_GIT_TUIS if shutil.which(tool)]


@dataclass
class TmuxLaunchConfig:
    """Configuration for launching a command in tmux."""

    session: str
    window: str
    new_session: bool
    new_window: bool
    split_direction: str = "horizontal"  # only used when new_window=False
    # Working directory for the new tmux pane. When set, ``launch_in_tmux``
    # passes ``-c <cwd>`` to tmux so the launched command runs in this dir
    # rather than inheriting the calling pane's cwd. Required for cross-
    # session launches where the target project_root differs from the
    # caller's cwd (e.g., monitor in project A picking a sibling task in
    # project B's tmux session).
    cwd: str | None = None


@dataclass(frozen=True)
class AitasksSession:
    """A tmux session identified as belonging to an aitasks project.

    Produced by :func:`discover_aitasks_sessions` when a session's pane cwd
    walks up into an aitasks project root, or when the session's name matches
    an ``AITASKS_PROJECT_<sess>`` global env entry set by ``ait ide``.

    When ``include_registered=True`` is passed to
    :func:`discover_aitasks_sessions`, synthesized entries are also produced
    from the per-user registry at ``~/.config/aitasks/projects.yaml``; those
    carry ``is_live=False`` and their ``session`` field is the project's
    configured tmux session name (resolved from its ``project_config.yaml``).
    STALE registry rows (path missing the
    ``aitasks/metadata/project_config.yaml`` marker) additionally carry
    ``is_stale=True`` so downstream UIs can render them distinctly.
    """

    session: str           # tmux session name
    project_root: Path     # absolute path to the project root
    project_name: str      # basename(project_root), for display
    is_live: bool = True   # False when synthesized from the per-user registry
    is_stale: bool = False # True when synthesized from a STALE registry row


def find_terminal() -> str | None:
    """Find an available terminal emulator, or return None."""
    terminal = os.environ.get("TERMINAL")
    if terminal and shutil.which(terminal):
        return terminal
    for term in [
        "alacritty", "kitty", "ghostty", "foot",
        "x-terminal-emulator", "xdg-terminal-exec", "gnome-terminal",
        "konsole", "xfce4-terminal", "lxterminal", "mate-terminal", "xterm",
    ]:
        if shutil.which(term):
            return term
    return None


def resolve_dry_run_command(
    project_root: Path,
    operation: str,
    *args: str,
    agent_string: str | None = None,
) -> str | None:
    """Resolve the full agent command via --dry-run.

    Calls aitask_codeagent.sh --dry-run invoke <operation> <args> and parses
    the DRY_RUN: <cmd> output. When `agent_string` is provided, prepends
    `--agent-string <value>` before --dry-run so the wrapper resolves the
    command for a non-default agent/model. Returns the command string or
    None on failure.
    """
    wrapper = str(project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    cmd = [wrapper]
    if agent_string:
        cmd += ["--agent-string", agent_string]
    cmd += ["--dry-run", "invoke", operation] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output.startswith("DRY_RUN: "):
                return output[len("DRY_RUN: "):]
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def resolve_agent_string(project_root: Path, operation: str) -> str | None:
    """Return the resolved agent string for an operation.

    Shells `aitask_codeagent.sh resolve <operation>` and parses the
    `AGENT_STRING:<value>` line. Returns the agent string or None on failure.
    """
    wrapper = str(project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    try:
        result = subprocess.run(
            [wrapper, "resolve", operation],
            capture_output=True, text=True, timeout=10,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("AGENT_STRING:"):
                    return line[len("AGENT_STRING:"):].strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def is_tmux_available() -> bool:
    """Check if tmux is installed."""
    return shutil.which("tmux") is not None


def get_tmux_sessions() -> list[str]:
    """List running tmux session names. Returns empty list if tmux not running."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return [s for s in result.stdout.strip().splitlines() if s]
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def get_tmux_windows(session: str) -> list[tuple[str, str]]:
    """List windows in a tmux session as (index, name) tuples."""
    try:
        result = subprocess.run(
            ["tmux", "list-windows", "-t", tmux_session_target(session),
             "-F", "#{window_index}:#{window_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            windows = []
            for line in result.stdout.strip().splitlines():
                if ":" in line:
                    idx, name = line.split(":", 1)
                    windows.append((idx, name))
            return windows
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def find_window_by_name(name: str, session: str) -> tuple[str, str] | None:
    """Find a tmux window by name within a specific session.

    Returns (session, window_index) if found, None otherwise. The session
    parameter is required to prevent cross-project matches — the aitasks
    framework is designed to run one tmux session per project, so whole-
    server scans are always a bug.
    """
    for idx, win_name in get_tmux_windows(session):
        if win_name == name:
            return (session, idx)
    return None


def _walk_up_to_aitasks(path: Path) -> Path | None:
    """Walk up from ``path`` (inclusive) until finding an aitasks project root.

    An aitasks project root is any directory containing
    ``aitasks/metadata/project_config.yaml``. Returns the matching directory
    or ``None`` if no ancestor qualifies.
    """
    for p in (path, *path.parents):
        if (p / "aitasks" / "metadata" / "project_config.yaml").is_file():
            return p
    return None


def _read_registry_entry(session: str) -> Path | None:
    """Read ``AITASKS_PROJECT_<session>`` from tmux global env.

    Returns the registered project root if the entry exists and points to a
    directory containing an aitasks project; otherwise ``None``. Handles the
    three tmux output forms: ``VAR=value`` (set), ``-VAR`` (unset marker), and
    empty stdout with non-zero exit (truly absent).
    """
    var = f"AITASKS_PROJECT_{session}"
    try:
        result = subprocess.run(
            ["tmux", "show-environment", "-g", var],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    line = result.stdout.strip()
    if not line or line.startswith("-") or "=" not in line:
        return None
    _, _, value = line.partition("=")
    value = value.strip()
    if not value:
        return None
    path = Path(value)
    if not (path / "aitasks" / "metadata" / "project_config.yaml").is_file():
        return None
    return path


def _read_registry_index() -> list[tuple[str, Path, str]]:
    """Read ``~/.config/aitasks/projects.yaml`` as ``(name, path, status)`` triples.

    Mirrors ``aitask_projects.sh::list_registry_entries`` with a simple line
    parser — no PyYAML dependency. Honors the ``AITASKS_PROJECTS_INDEX``
    env var (same override the bash side supports). Annotates each entry
    with ``"OK"`` (path holds the ``aitasks/metadata/project_config.yaml``
    marker) or ``"STALE"`` (marker missing) so downstream callers can
    decide whether to render or skip.
    """
    index_path = os.environ.get("AITASKS_PROJECTS_INDEX")
    if not index_path:
        index_path = os.path.expanduser("~/.config/aitasks/projects.yaml")
    if not os.path.isfile(index_path):
        return []

    def _unquote(s: str) -> str:
        s = s.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
            s = s[1:-1]
        return s

    entries: list[tuple[str, Path, str]] = []
    cur_name = ""
    cur_path = ""

    def _flush() -> None:
        nonlocal cur_name, cur_path
        if cur_name and cur_path:
            p = Path(cur_path)
            if (p / "aitasks" / "metadata" / "project_config.yaml").is_file():
                entries.append((cur_name, p, "OK"))
            else:
                entries.append((cur_name, p, "STALE"))
        cur_name = ""
        cur_path = ""

    try:
        with open(index_path, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.rstrip("\n")
                stripped = line.lstrip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("- name:"):
                    _flush()
                    cur_name = _unquote(stripped[len("- name:"):])
                    continue
                if stripped.startswith("name:") and line.startswith(" "):
                    _flush()
                    cur_name = _unquote(stripped[len("name:"):])
                    continue
                if stripped.startswith("path:") and line.startswith(" "):
                    cur_path = _unquote(stripped[len("path:"):])
                    continue
        _flush()
    except OSError:
        return []

    return entries


def _read_default_session(project_root: Path) -> str:
    """Read ``tmux.default_session`` from a project's config; default ``aitasks``.

    Mirrors ``aitask_ide.sh::resolve_session`` (lines 46-72), reading the
    top-level ``tmux:`` block and its ``default_session:`` child. Falls back
    to the literal ``"aitasks"`` when the field is absent (matching the bash
    default), so an unconfigured project's effective session name is stable
    across the live-tmux scan and the registry-synthesis path.
    """
    cfg = project_root / "aitasks" / "metadata" / "project_config.yaml"
    if not cfg.is_file():
        return "aitasks"

    def _unquote(s: str) -> str:
        s = s.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
            s = s[1:-1]
        return s

    in_tmux_block = False
    try:
        with open(cfg, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.rstrip("\n")
                if not line or line.lstrip().startswith("#"):
                    continue
                # Top-level non-comment line: enter / exit tmux: block.
                if line[:1] not in (" ", "\t"):
                    in_tmux_block = line.startswith("tmux:")
                    continue
                if not in_tmux_block:
                    continue
                stripped = line.lstrip()
                if stripped.startswith("default_session:"):
                    val = _unquote(stripped[len("default_session:"):])
                    if val:
                        return val
                    break
    except OSError:
        pass
    return "aitasks"


def discover_aitasks_sessions(
    *, include_registered: bool = False
) -> list[AitasksSession]:
    """Enumerate aitasks-like tmux sessions on the current tmux server.

    Detection is per-session in priority order:

    1. **Pane-cwd walk-up** — any pane's ``pane_current_path`` that has an
       ancestor containing ``aitasks/metadata/project_config.yaml`` wins.
    2. **Registry fallback** — the tmux global env var
       ``AITASKS_PROJECT_<sess>`` (set by ``ait ide`` on startup) names the
       project root directly.

    Sessions matching neither heuristic are excluded. Returns a list sorted by
    session name for stable display. Returns an empty list when tmux is
    unavailable or no aitasks sessions are running. No module-level caching —
    each call re-queries tmux so long-running monitors see live state.

    When ``include_registered=True``, additionally emits synthesized entries
    for every registered project in ``~/.config/aitasks/projects.yaml`` that
    is not already covered by a live session (deduped on ``project_name``).
    Synthesized entries carry ``is_live=False`` and a ``session`` field
    resolved from each project's ``tmux.default_session`` config; STALE
    registry rows (path missing the marker file) additionally carry
    ``is_stale=True``. Default ``False`` so existing callers (notably
    ``ait monitor``) see identical output to today.
    """
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
        sessions = (
            [s for s in result.stdout.strip().splitlines() if s]
            if result.returncode == 0 else []
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        sessions = []

    found: list[AitasksSession] = []
    for session in sessions:
        project_root: Path | None = None
        try:
            panes = subprocess.run(
                ["tmux", "list-panes", "-s", "-t",
                 tmux_session_target(session),
                 "-F", "#{pane_current_path}"],
                capture_output=True, text=True, timeout=5,
            )
            if panes.returncode == 0:
                for raw_path in panes.stdout.strip().splitlines():
                    if not raw_path:
                        continue
                    candidate = _walk_up_to_aitasks(Path(raw_path))
                    if candidate is not None:
                        project_root = candidate
                        break
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        if project_root is None:
            project_root = _read_registry_entry(session)

        if project_root is None:
            continue

        found.append(AitasksSession(
            session=session,
            project_root=project_root,
            project_name=project_root.name,
        ))

    if include_registered:
        live_names = {s.project_name for s in found}
        for name, root, status in _read_registry_index():
            if name in live_names:
                continue
            found.append(AitasksSession(
                session=_read_default_session(root),
                project_root=root,
                project_name=name,
                is_live=False,
                is_stale=(status == "STALE"),
            ))

    found.sort(key=lambda s: s.session)
    return found


def switch_to_pane_anywhere(pane_id: str) -> bool:
    """Teleport the attached tmux client to an arbitrary pane on this server.

    Pane IDs are server-globally unique, so no session hint is required. The
    function resolves the pane's session and window index via
    ``display-message``, then issues ``switch-client``, ``select-window``, and
    ``select-pane`` in order. The first non-zero exit returns ``False``.
    Returns ``True`` on success; ``False`` if tmux is unavailable, the pane is
    dead, or no client is attached.
    """
    def _display(fmt: str) -> str | None:
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "-t", pane_id, fmt],
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    sess = _display("#{session_name}")
    if not sess:
        return False
    win = _display("#{window_index}")
    if not win:
        return False

    for args in (
        ["switch-client", "-t", tmux_session_target(sess)],
        ["select-window", "-t", tmux_window_target(sess, win)],
        ["select-pane", "-t", pane_id],
    ):
        try:
            result = subprocess.run(
                ["tmux", *args],
                capture_output=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
        if result.returncode != 0:
            return False
    return True


def _parse_pane_pid(stdout: str) -> int | None:
    """Parse the first line of tmux ``-P -F`` output as an int pid, or None."""
    stripped = stdout.strip()
    if not stripped:
        return None
    line = stripped.splitlines()[0]
    try:
        return int(line)
    except ValueError:
        return None


def _query_first_pane_pid(session: str, window: str) -> int | None:
    """Query the first pane's pid in a freshly created session/window."""
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", tmux_window_target(session, window),
             "-F", "#{pane_pid}"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    return _parse_pane_pid(result.stdout)


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
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    return result.returncode == 0 or result.stdout.strip() == "degraded"


def _persistent_new_session_prefix(session: str) -> list[str] | None:
    """systemd-run argv prefix that lands a new tmux SERVER in a persistent
    ``session.slice`` service, or ``None`` when ``systemd --user`` is
    unavailable.

    Python mirror of the systemd-run rung of ``ait_tmux_new_session_persistent``
    (t943): the new server escapes the transient ``app.slice`` scope so a
    compositor / ``app.slice`` teardown can no longer reap it (t956). Socket
    unchanged (default). The returned prefix is meant to be concatenated with a
    ``tmux new-session -d …`` argv.
    """
    if not _systemd_user_available():
        return None
    safe = "session"
    try:
        esc = subprocess.run(
            ["systemd-escape", "--", session],
            capture_output=True, text=True, timeout=5,
        )
        if esc.returncode == 0 and esc.stdout.strip():
            safe = esc.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    # --slice=session.slice is the load-bearing flag (escapes app.slice).
    # Type=forking matches tmux's double-fork; KillMode=none keeps systemd from
    # signalling the server cgroup when the launching transaction finishes;
    # --collect GCs the unit in the benign loser-of-a-race case.
    unit = f"ait-tmux-{safe}-{os.getpid()}-{os.urandom(3).hex()}"
    return [
        "systemd-run", "--user", "--slice=session.slice", f"--unit={unit}",
        "--property=Type=forking", "--property=KillMode=none",
        "--collect", "--quiet", "--",
    ]


def _new_session_tmux_argv(
    session: str, window: str, command: str,
    cwd_args: list[str], cwd: str | None,
) -> list[str]:
    """Build the argv that creates a detached tmux session.

    When this call genuinely creates the tmux SERVER (no server running yet),
    wrap it in a persistent ``session.slice`` systemd-user service so a
    compositor / ``app.slice`` teardown can't reap it (t956, mirroring t943's
    ``ait_tmux_new_session_persistent``), with a setsid → plain-tmux fallback
    ladder. When a server is already running this is an *attach*, not a server
    creation, so today's plain invocation is used unchanged.
    """
    base = ["tmux", "new-session", "-d", "-s", session, "-n", window]
    if get_tmux_sessions():
        # A tmux server is already running → new-session attaches a session to
        # it (no server creation). Preserve today's default-cwd behavior — no
        # forced -c when cwd is None.
        return base + cwd_args + [command]
    # No server running → this new-session creates it. The systemd-run / setsid
    # rungs sever the launcher relationship, so pass an explicit -c: once
    # detached, the default "inherit the launcher's cwd" no longer holds, and
    # ``cwd or os.getcwd()`` reproduces today's inherited-cwd behavior.
    created = base + ["-c", cwd or os.getcwd(), command]
    prefix = _persistent_new_session_prefix(session)
    if prefix is not None:
        return prefix + created
    if shutil.which("setsid"):
        return ["setsid"] + created
    return created


def launch_in_tmux(command: str, config: TmuxLaunchConfig) -> tuple[int | None, str | None]:
    """Launch a command in tmux according to the given config.

    Returns ``(pane_pid, error)``. ``pane_pid`` is the PID of the process
    tmux fork-exec'd inside the spawned pane (i.e. the agent process), or
    ``None`` if the launch succeeded but the pid could not be captured.
    ``error`` is ``None`` on success, otherwise a human-readable message
    describing the tmux failure.
    """
    cwd_args = ["-c", config.cwd] if config.cwd else []
    if config.new_session:
        # Create new session with a window, then switch to it. When this is the
        # first session (no server yet), the server is spawned inside a
        # persistent session.slice service so it survives an app.slice teardown
        # (t956) — see _new_session_tmux_argv. ``new-session -d`` does not
        # support ``-P``, so query pane_pid from list-panes after creation.
        tmux_cmd = _new_session_tmux_argv(
            config.session, config.window, command, cwd_args, config.cwd,
        )
        proc = subprocess.Popen(tmux_cmd, stderr=subprocess.PIPE)
        proc.wait()
        if proc.returncode != 0:
            stderr = proc.stderr.read().decode() if proc.stderr else ""
            return None, f"tmux new-session failed: {stderr}"
        pane_pid = _query_first_pane_pid(config.session, config.window)
        # Try to switch client (works if we're inside tmux)
        if os.environ.get("TMUX"):
            subprocess.Popen(
                ["tmux", "switch-client", "-t", tmux_session_target(config.session)]
            )
        return pane_pid, None
    elif config.new_window:
        tmux_cmd = [
            "tmux", "new-window",
            "-P", "-F", "#{pane_pid}",
            "-t", tmux_window_target(config.session, ""),
            "-n", config.window,
            *cwd_args,
            command,
        ]
        try:
            result = subprocess.run(
                tmux_cmd, capture_output=True, text=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return None, f"tmux new-window failed: {e}"
        if result.returncode != 0:
            return None, f"tmux new-window failed: {result.stderr.strip()}"
        return _parse_pane_pid(result.stdout), None
    else:
        # Split existing window into a new pane
        split_flag = "-h" if config.split_direction == "horizontal" else "-v"
        target = tmux_window_target(config.session, config.window)
        tmux_cmd = [
            "tmux", "split-window",
            "-P", "-F", "#{pane_pid}",
            split_flag, "-t", target,
            *cwd_args,
            command,
        ]
        try:
            result = subprocess.run(
                tmux_cmd, capture_output=True, text=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            return None, f"tmux split-window failed: {e}"
        if result.returncode != 0:
            return None, f"tmux split-window failed: {result.stderr.strip()}"
        # Switch to the target window so the user sees the new pane
        subprocess.Popen(["tmux", "select-window", "-t", target])
        return _parse_pane_pid(result.stdout), None


def _lookup_window_name(session: str, window_index: str) -> str | None:
    """Look up a tmux window name from its index."""
    try:
        result = subprocess.run(
            ["tmux", "list-windows", "-t", tmux_session_target(session),
             "-F", "#{window_index}:#{window_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.strip().splitlines():
            if ":" in line:
                idx, name = line.split(":", 1)
                if idx == window_index:
                    return name
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def maybe_spawn_minimonitor(
    session: str,
    window_name: str,
    *,
    window_index: str | None = None,
    force_companion: bool = False,
    project_root: Path | None = None,
) -> str | None:
    """Spawn a minimonitor split pane if conditions are met.

    Called after launch_in_tmux() creates a new window or splits into an
    existing one. Spawns a companion minimonitor pane when the window name
    matches a configured prefix and the window does not already contain a
    monitor/minimonitor or TUI process.

    Args:
        session: tmux session name
        window_name: tmux window name (for prefix matching and TUI exclusion)
        window_index: if provided, skip the name→index lookup (existing-window case)
        force_companion: if True, bypass the companion-prefix check and the
            TUI-name/brainstorm exclusion check. Used for dynamic companion
            flows like the git TUI where the window name ("git") is not
            prefix-based and is also classified as a TUI in the registry. The
            `auto_spawn`, existing-minimonitor, and pane-count guards still
            apply.
        project_root: when set, read ``project_config.yaml`` and pass
            ``-c <project_root>`` to ``tmux split-window`` so the companion
            pane starts in that project's directory. Required for cross-
            session spawns from the TUI switcher; defaults to ``Path.cwd()``
            for legacy callers operating on the current project.

    Returns the new companion pane id (e.g. `%42`) on success, or None if
    no spawn happened (disabled, rejected by a gate, tmux error, etc.).
    """
    # Read config from project_config.yaml
    auto_spawn = True
    width = 40
    companion_prefixes = ["agent-", "create-"]
    tui_names = set(_DEFAULT_TUI_NAMES)
    cfg_root = project_root if project_root is not None else Path.cwd()
    config_path = cfg_root / "aitasks" / "metadata" / "project_config.yaml"
    if config_path.is_file():
        try:
            import yaml
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            tmux = data.get("tmux", {})
            if isinstance(tmux, dict):
                mm = tmux.get("minimonitor", {})
                if isinstance(mm, dict):
                    if "auto_spawn" in mm:
                        auto_spawn = bool(mm["auto_spawn"])
                    if "width" in mm:
                        width = int(mm["width"])
                    if "companion_window_prefixes" in mm:
                        companion_prefixes = list(mm["companion_window_prefixes"])
                monitor = tmux.get("monitor", {})
                if isinstance(monitor, dict):
                    if "tui_window_names" in monitor:
                        # Merge with registry defaults so new framework TUIs
                        # are never masked by a stale override list.
                        tui_names = set(_DEFAULT_TUI_NAMES) | set(monitor["tui_window_names"])
        except Exception:
            pass

    if not auto_spawn:
        return None

    if not force_companion:
        # Check window name matches an eligible companion prefix
        if not any(window_name.startswith(p) for p in companion_prefixes):
            return None

        # Exclude TUI windows (board, codebrowser, monitor, etc.)
        if window_name in tui_names or window_name.startswith("brainstorm-"):
            return None

    # Resolve window index
    win_index = window_index
    if win_index is None:
        try:
            result = subprocess.run(
                ["tmux", "list-windows", "-t", tmux_session_target(session),
                 "-F", "#{window_index}:#{window_name}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
            for line in result.stdout.strip().splitlines():
                if ":" in line:
                    idx, name = line.split(":", 1)
                    if name == window_name:
                        win_index = idx  # keep looping — pick the *last* match
            if win_index is None:
                return None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

    # Check existing panes for monitor/minimonitor and pane count
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-t", tmux_window_target(session, win_index),
             "-F", "#{pane_current_command}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            pane_lines = result.stdout.strip().splitlines()
            for cmd_line in pane_lines:
                if "minimonitor" in cmd_line or "monitor_app" in cmd_line:
                    return None
            # Avoid overcrowding: skip if 3+ panes already exist
            if len(pane_lines) >= 3:
                return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Spawn minimonitor as a right split, capturing the new pane id
    split_argv = ["tmux", "split-window", "-h", "-P", "-F", "#{pane_id}",
                  "-l", str(width)]
    if project_root is not None:
        split_argv += ["-c", str(project_root)]
    split_argv += ["-t", tmux_window_target(session, win_index),
                   "ait", "minimonitor"]
    try:
        spawn = subprocess.run(
            split_argv,
            capture_output=True, text=True, timeout=5,
        )
        if spawn.returncode != 0:
            return None
        companion_pane = spawn.stdout.strip() or None
        # Refocus the original pane (left pane)
        subprocess.Popen(
            ["tmux", "select-pane", "-t",
             f"{tmux_window_target(session, win_index)}.0"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return companion_pane
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def launch_or_focus_codebrowser(
    session: str,
    focus_value: str,
    window_name: str = "codebrowser",
) -> tuple[bool, str | None]:
    """Set the focus env var and bring the codebrowser to the given range.

    If a window named *window_name* already exists in *session*, selects
    it; otherwise creates a new window running ``./ait codebrowser --focus
    <focus_value>``. The env var is set first so both the reuse and the
    cold-launch paths see it.

    Returns ``(success, error_message)``. On success, error_message is None.
    """
    try:
        result = subprocess.run(
            ["tmux", "set-environment", "-t", tmux_session_target(session),
             "AITASK_CODEBROWSER_FOCUS", focus_value],
            capture_output=True, timeout=5,
        )
        if result.returncode != 0:
            return False, "tmux set-environment failed"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, f"tmux set-environment error: {e}"

    try:
        lw = subprocess.run(
            ["tmux", "list-windows", "-t", tmux_session_target(session),
             "-F", "#{window_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if lw.returncode != 0:
            return False, "tmux list-windows failed"
        names = lw.stdout.strip().splitlines()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, f"tmux list-windows error: {e}"

    try:
        if window_name in names:
            sel = subprocess.run(
                ["tmux", "select-window", "-t",
                 tmux_window_target(session, window_name)],
                capture_output=True, timeout=5,
            )
            if sel.returncode != 0:
                return False, "tmux select-window failed"
        else:
            nw = subprocess.run(
                ["tmux", "new-window", "-t", tmux_window_target(session, ""),
                 "-n", window_name,
                 "./ait", "codebrowser", "--focus", focus_value],
                capture_output=True, timeout=5,
            )
            if nw.returncode != 0:
                return False, "tmux new-window failed"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, f"tmux switch error: {e}"

    return True, None


def load_tmux_defaults(project_root: Path) -> dict:
    """Load tmux defaults from project_config.yaml.

    Returns dict with keys: default_session, default_split, prefer_tmux,
    git_tui, syncer_autostart. Falls back to hardcoded defaults if config is
    absent.
    """
    defaults = {
        "default_session": "aitasks",
        "default_split": "horizontal",
        "prefer_tmux": False,
        "git_tui": "",
        "syncer_autostart": False,
    }
    config_path = project_root / "aitasks" / "metadata" / "project_config.yaml"
    if not config_path.is_file():
        return defaults
    try:
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        tmux = data.get("tmux", {})
        if isinstance(tmux, dict):
            if "default_session" in tmux:
                defaults["default_session"] = str(tmux["default_session"])
            if "default_split" in tmux:
                val = str(tmux["default_split"]).lower()
                if val in ("horizontal", "vertical"):
                    defaults["default_split"] = val
            if "prefer_tmux" in tmux:
                defaults["prefer_tmux"] = bool(tmux["prefer_tmux"])
            if "git_tui" in tmux:
                defaults["git_tui"] = str(tmux["git_tui"] or "")
            syncer = tmux.get("syncer")
            if isinstance(syncer, dict) and "autostart" in syncer:
                defaults["syncer_autostart"] = bool(syncer["autostart"])
    except Exception:
        pass
    return defaults
