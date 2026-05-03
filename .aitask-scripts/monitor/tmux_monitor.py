"""tmux_monitor - Core monitoring library for tmux pane discovery and tracking.

Non-UI module (no Textual dependency). Provides pane discovery, content capture,
idle detection, and pane categorization for tmux sessions.

Usage:
    from monitor.tmux_monitor import TmuxMonitor, load_monitor_config

    config = load_monitor_config(project_root)
    monitor = TmuxMonitor(session="aitasks", **config)
    snapshots = monitor.capture_all()
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tmux_control import TmuxControlBackend

_LIB_DIR = str(Path(__file__).resolve().parent.parent / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from tui_registry import BRAINSTORM_PREFIX, TUI_NAMES  # noqa: E402
from agent_launch_utils import (  # noqa: E402
    AitasksSession,
    discover_aitasks_sessions,
    switch_to_pane_anywhere,
    tmux_session_target,
    tmux_window_target,
)


class PaneCategory(Enum):
    AGENT = "agent"
    TUI = "tui"
    OTHER = "other"


DEFAULT_AGENT_PREFIXES = ["agent-"]
DEFAULT_TUI_NAMES = TUI_NAMES

# Idle-detection comparison modes.
#   stripped — strip ANSI escape codes from captured pane content before
#     equality check. Required to detect Codex CLI agents as idle: Codex
#     animates the spinner color via SGR escape codes even while waiting
#     on user input, so a raw byte-equal comparison declares the pane
#     "changed" every refresh tick and idle is never reached.
#   raw — compare the full captured bytes including escape codes. Legacy
#     behavior; only useful as a fallback if a future agent renders idle
#     UI by toggling escape codes that semantically matter.
COMPARE_MODE_STRIPPED = "stripped"
COMPARE_MODE_RAW = "raw"
COMPARE_MODES = (COMPARE_MODE_STRIPPED, COMPARE_MODE_RAW)
DEFAULT_COMPARE_MODE = COMPARE_MODE_STRIPPED

# CSI escape sequence (covers SGR colors plus any other animated CSI tokens).
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(s: str) -> str:
    return _ANSI_CSI_RE.sub("", s)


_COMPANION_KEYWORDS = ("minimonitor", "monitor_app")


def _is_companion_process(pid: int) -> bool:
    """Check if a process is a companion pane (minimonitor/monitor) via cmdline."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmdline = f.read().decode("utf-8", errors="replace")
        return any(kw in cmdline for kw in _COMPANION_KEYWORDS)
    except (OSError, PermissionError):
        pass
    # Fallback for non-Linux (macOS)
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            return any(kw in result.stdout for kw in _COMPANION_KEYWORDS)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return False


async def _run_tmux_async(args: list[str], timeout: float = 5.0) -> tuple[int, str]:
    """Run `tmux <args>` asynchronously. Returns (returncode, stdout_text).

    Returns (-1, "") on FileNotFoundError / OSError / timeout, matching the
    error semantics of the synchronous tmux helpers (they just return empty
    on failure).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "tmux", *args,
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


def _run_tmux_subprocess(
    args: list[str], timeout: float = 5.0
) -> tuple[int, str]:
    """Sync sibling of `_run_tmux_async`. Same `(rc, stdout)` contract.

    `(-1, "")` on FileNotFoundError / OSError / timeout. Used as the
    subprocess fallback path inside `TmuxMonitor.tmux_run`, and (post-t722)
    is the *only* place in `.aitask-scripts/monitor/` that spawns tmux via
    `subprocess.run` for runtime ops — every other site routes through
    `tmux_run` or `_tmux_async`. (The two `_detect_tmux_session()`
    pre-monitor-init helpers in `monitor_app.py` and `minimonitor_app.py`
    are the only intentional exceptions; no `TmuxMonitor` exists yet at
    that point.)
    """
    try:
        result = subprocess.run(
            ["tmux", *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return (-1, "")
    return (result.returncode, result.stdout or "")


@dataclass
class TmuxPaneInfo:
    window_index: str
    window_name: str
    pane_index: str
    pane_id: str        # e.g., %3
    pane_pid: int
    current_command: str
    width: int
    height: int
    category: PaneCategory
    session_name: str = ""   # populated by discovery; "" only when constructed outside a list-panes path


@dataclass
class PaneSnapshot:
    pane: TmuxPaneInfo
    content: str            # last N lines of captured text
    timestamp: float        # time.monotonic()
    idle_seconds: float     # seconds since last content change
    is_idle: bool           # idle_seconds > threshold (only meaningful for AGENT panes)


class TmuxMonitor:
    # Session-discovery cache TTL: `discover_aitasks_sessions()` runs `tmux
    # list-sessions` plus a serial `list-panes -s` per session, which is
    # wasteful to redo every refresh tick. Ten seconds keeps the view snappy
    # without re-querying on every paint. The `M` runtime toggle invalidates
    # the cache so the first post-toggle refresh re-discovers immediately.
    _SESSIONS_CACHE_TTL = 10.0

    def __init__(
        self,
        session: str,
        capture_lines: int = 200,
        idle_threshold: float = 5.0,
        exclude_pane: str | None = None,
        agent_prefixes: list[str] | None = None,
        tui_names: set[str] | None = None,
        multi_session: bool = True,
        compare_mode_default: str = DEFAULT_COMPARE_MODE,
    ):
        self.session = session
        self.capture_lines = capture_lines
        self.idle_threshold = idle_threshold
        self.exclude_pane = exclude_pane or os.environ.get("TMUX_PANE")
        self.agent_prefixes = agent_prefixes if agent_prefixes is not None else list(DEFAULT_AGENT_PREFIXES)
        self.tui_names = tui_names if tui_names is not None else set(DEFAULT_TUI_NAMES)
        self.multi_session = multi_session
        if compare_mode_default not in COMPARE_MODES:
            compare_mode_default = DEFAULT_COMPARE_MODE
        self.compare_mode_default = compare_mode_default

        self._last_content: dict[str, str] = {}
        self._last_change_time: dict[str, float] = {}
        self._pane_cache: dict[str, TmuxPaneInfo] = {}
        self._sessions_cache: tuple[float, list[AitasksSession]] | None = None
        self._compare_mode_overrides: dict[str, str] = {}
        self._backend: TmuxControlBackend | None = None

    async def start_control_client(self) -> bool:
        """Start the persistent `tmux -C` backend on a dedicated bg thread.

        Kept `async` so existing call sites (`await monitor.start_control_client()`)
        do not need to change. The body is synchronous — the bg thread does
        the actual asyncio work — so awaiting it just yields once.
        """
        from .tmux_control import TmuxControlBackend
        backend = TmuxControlBackend(session=self.session)
        if backend.start():
            self._backend = backend
            return True
        backend.stop()
        return False

    async def close_control_client(self) -> None:
        if self._backend is not None:
            with contextlib.suppress(Exception):
                self._backend.stop()
            self._backend = None

    def has_control_client(self) -> bool:
        return self._backend is not None and self._backend.is_alive

    async def _tmux_async(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        backend = self._backend
        if backend is not None and backend.is_alive:
            rc, out = await backend.request_async(args, timeout=timeout)
            if rc != -1:
                return rc, out
            # transport failure on this call — fall back to subprocess.
        return await _run_tmux_async(args, timeout=timeout)

    def tmux_run(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        """Sync user-action wrapper — control-client when alive, subprocess fallback.

        Returns `(rc, stdout)`. `rc` semantics match `_tmux_async`:
          * `0` on success
          * `1` on tmux command error
          * `-1` on transport failure or subprocess error.

        Safe to call from sync Textual handlers because the control client
        runs on a background loop; this method blocks the caller's thread,
        not the bg loop's reader task.
        """
        backend = self._backend
        if backend is not None and backend.is_alive:
            rc, out = backend.request_sync(args, timeout=timeout)
            if rc != -1:
                return rc, out
        return _run_tmux_subprocess(args, timeout=timeout)

    def _discover_sessions_cached(self) -> list[AitasksSession]:
        """Return the list of aitasks-like tmux sessions, memoized for TTL seconds."""
        now = time.monotonic()
        if self._sessions_cache is not None:
            cached_at, sessions = self._sessions_cache
            if now - cached_at < self._SESSIONS_CACHE_TTL:
                return sessions
        sessions = discover_aitasks_sessions()
        self._sessions_cache = (now, sessions)
        return sessions

    def invalidate_sessions_cache(self) -> None:
        """Force the next `_discover_sessions_cached` call to re-query tmux."""
        self._sessions_cache = None

    def get_session_to_project_mapping(self) -> dict[str, Path]:
        """Map session_name → project_root for all discovered aitasks sessions.

        Piggybacks on the `_discover_sessions_cached` TTL — no extra tmux
        calls. Used by monitor TUIs to resolve task data from the project that
        owns each codeagent's tmux session.
        """
        return {s.session: s.project_root for s in self._discover_sessions_cached()}

    def classify_pane(self, window_name: str) -> PaneCategory:
        for prefix in self.agent_prefixes:
            if window_name.startswith(prefix):
                return PaneCategory.AGENT
        if window_name in self.tui_names:
            return PaneCategory.TUI
        if window_name.startswith(BRAINSTORM_PREFIX):
            return PaneCategory.TUI
        return PaneCategory.OTHER

    _LIST_PANES_FORMAT = "\t".join([
        "#{window_index}", "#{window_name}", "#{pane_index}",
        "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
        "#{pane_width}", "#{pane_height}",
    ])

    def _parse_list_panes(self, stdout: str, session_name: str) -> list[TmuxPaneInfo]:
        panes: list[TmuxPaneInfo] = []
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 8:
                continue
            pane_id = parts[3]
            if self.exclude_pane and pane_id == self.exclude_pane:
                continue
            try:
                pane_pid = int(parts[4])
                width = int(parts[6])
                height = int(parts[7])
            except ValueError:
                continue
            window_name = parts[1]
            category = self.classify_pane(window_name)
            # Filter companion panes (minimonitor/monitor) in agent windows
            if category == PaneCategory.AGENT and _is_companion_process(pane_pid):
                continue
            pane = TmuxPaneInfo(
                window_index=parts[0],
                window_name=window_name,
                pane_index=parts[2],
                pane_id=pane_id,
                pane_pid=pane_pid,
                current_command=parts[5],
                width=width,
                height=height,
                category=category,
                session_name=session_name,
            )
            panes.append(pane)
            self._pane_cache[pane_id] = pane
        return panes

    def _target_sessions(self) -> list[str]:
        """Session names to enumerate in multi mode (sorted for stable display)."""
        return sorted(s.session for s in self._discover_sessions_cached())

    def _discover_panes_multi(self) -> list[TmuxPaneInfo]:
        panes: list[TmuxPaneInfo] = []
        for sess in self._target_sessions():
            rc, stdout = self.tmux_run([
                "list-panes", "-s", "-t", tmux_session_target(sess),
                "-F", self._LIST_PANES_FORMAT,
            ])
            if rc != 0:
                continue
            panes.extend(self._parse_list_panes(stdout, sess))
        panes.sort(key=lambda p: (p.session_name, p.window_index, p.pane_index))
        return panes

    async def _discover_panes_multi_async(self) -> list[TmuxPaneInfo]:
        sessions = self._target_sessions()
        if not sessions:
            return []
        results = await asyncio.gather(*[
            self._tmux_async([
                "list-panes", "-s", "-t", tmux_session_target(sess),
                "-F", self._LIST_PANES_FORMAT,
            ])
            for sess in sessions
        ])
        panes: list[TmuxPaneInfo] = []
        for sess, (rc, stdout) in zip(sessions, results):
            if rc != 0:
                continue
            panes.extend(self._parse_list_panes(stdout, sess))
        panes.sort(key=lambda p: (p.session_name, p.window_index, p.pane_index))
        return panes

    def discover_panes(self) -> list[TmuxPaneInfo]:
        if self.multi_session:
            return self._discover_panes_multi()
        rc, stdout = self.tmux_run([
            "list-panes", "-s", "-t", tmux_session_target(self.session),
            "-F", self._LIST_PANES_FORMAT,
        ])
        if rc != 0:
            return []
        return self._parse_list_panes(stdout, self.session)

    async def discover_panes_async(self) -> list[TmuxPaneInfo]:
        if self.multi_session:
            return await self._discover_panes_multi_async()
        rc, stdout = await self._tmux_async(
            ["list-panes", "-s", "-t", tmux_session_target(self.session),
             "-F", self._LIST_PANES_FORMAT],
        )
        if rc != 0:
            return []
        return self._parse_list_panes(stdout, self.session)

    def discover_window_panes(self, window_id: str) -> list[TmuxPaneInfo]:
        """Discover panes in a specific window (not session-wide).

        Uses 'tmux list-panes -t window_id' (no -s flag).
        Does not filter by exclude_pane or update _pane_cache.
        """
        fmt = "\t".join([
            "#{window_index}", "#{window_name}", "#{pane_index}",
            "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
            "#{pane_width}", "#{pane_height}",
        ])
        rc, stdout = self.tmux_run(["list-panes", "-t", window_id, "-F", fmt])
        if rc != 0:
            return []

        panes: list[TmuxPaneInfo] = []
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 8:
                continue
            try:
                pane_pid = int(parts[4])
                width = int(parts[6])
                height = int(parts[7])
            except ValueError:
                continue
            window_name = parts[1]
            pane = TmuxPaneInfo(
                window_index=parts[0],
                window_name=window_name,
                pane_index=parts[2],
                pane_id=parts[3],
                pane_pid=pane_pid,
                current_command=parts[5],
                width=width,
                height=height,
                category=self.classify_pane(window_name),
                session_name=self.session,
            )
            panes.append(pane)
        return panes

    def get_compare_mode(self, pane_id: str) -> str:
        """Effective idle-detection compare mode for a pane.

        Returns the per-pane override if set, otherwise the global default.
        """
        return self._compare_mode_overrides.get(pane_id, self.compare_mode_default)

    def is_compare_mode_overridden(self, pane_id: str) -> bool:
        return pane_id in self._compare_mode_overrides

    def set_compare_mode(self, pane_id: str, mode: str | None) -> str:
        """Set per-pane compare mode override; pass None to clear and follow default.

        Clears the stored last-content for the pane so the next capture
        re-baselines under the new comparison form, avoiding one tick of
        spurious "changed" right after the toggle.
        """
        if mode is None:
            self._compare_mode_overrides.pop(pane_id, None)
        else:
            if mode not in COMPARE_MODES:
                raise ValueError(f"unknown compare mode: {mode!r}")
            self._compare_mode_overrides[pane_id] = mode
        self._last_content.pop(pane_id, None)
        return self.get_compare_mode(pane_id)

    def cycle_compare_mode(self, pane_id: str) -> tuple[str, bool]:
        """Cycle a pane through default → raw → stripped → default.

        Returns (effective_mode, is_following_default).
        """
        current_override = self._compare_mode_overrides.get(pane_id)
        if current_override is None:
            new_override: str | None = COMPARE_MODE_RAW
        elif current_override == COMPARE_MODE_RAW:
            new_override = COMPARE_MODE_STRIPPED
        else:
            new_override = None
        effective = self.set_compare_mode(pane_id, new_override)
        return effective, (new_override is None)

    def _finalize_capture(
        self, pane: TmuxPaneInfo, content: str
    ) -> PaneSnapshot:
        now = time.monotonic()
        pane_id = pane.pane_id

        mode = self.get_compare_mode(pane_id)
        compare_value = _strip_ansi(content) if mode == COMPARE_MODE_STRIPPED else content

        prev = self._last_content.get(pane_id)
        if prev is None or compare_value != prev:
            self._last_content[pane_id] = compare_value
            self._last_change_time[pane_id] = now

        last_change = self._last_change_time.get(pane_id, now)
        idle_seconds = now - last_change
        is_idle = (
            idle_seconds > self.idle_threshold
            if pane.category == PaneCategory.AGENT
            else False
        )

        return PaneSnapshot(
            pane=pane,
            content=content,
            timestamp=now,
            idle_seconds=idle_seconds,
            is_idle=is_idle,
        )

    def _capture_args(self, pane_id: str) -> list[str]:
        return [
            "capture-pane", "-p", "-e", "-t", pane_id,
            "-S", f"-{self.capture_lines}",
        ]

    def capture_pane(self, pane_id: str) -> PaneSnapshot | None:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return None
        rc, content = self.tmux_run(self._capture_args(pane_id))
        if rc != 0:
            return None
        return self._finalize_capture(pane, content)

    async def capture_pane_async(self, pane_id: str) -> PaneSnapshot | None:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return None
        rc, content = await self._tmux_async(self._capture_args(pane_id))
        if rc != 0:
            return None
        return self._finalize_capture(pane, content)

    def _clean_stale(self, current_ids: set[str]) -> None:
        stale = [pid for pid in self._last_content if pid not in current_ids]
        for pid in stale:
            del self._last_content[pid]
            self._last_change_time.pop(pid, None)
            self._pane_cache.pop(pid, None)
        for pid in list(self._compare_mode_overrides):
            if pid not in current_ids:
                self._compare_mode_overrides.pop(pid, None)

    def capture_all(self) -> dict[str, PaneSnapshot]:
        panes = self.discover_panes()
        self._clean_stale({p.pane_id for p in panes})

        snapshots: dict[str, PaneSnapshot] = {}
        for pane in panes:
            snap = self.capture_pane(pane.pane_id)
            if snap is not None:
                snapshots[pane.pane_id] = snap
        return snapshots

    async def capture_all_async(self) -> dict[str, PaneSnapshot]:
        panes = await self.discover_panes_async()
        self._clean_stale({p.pane_id for p in panes})

        # Capture all panes concurrently; skip any that error out.
        results = await asyncio.gather(
            *(self.capture_pane_async(p.pane_id) for p in panes),
            return_exceptions=True,
        )
        snapshots: dict[str, PaneSnapshot] = {}
        for pane, snap in zip(panes, results):
            if isinstance(snap, PaneSnapshot):
                snapshots[pane.pane_id] = snap
        return snapshots

    def send_enter(self, pane_id: str) -> bool:
        rc, _ = self.tmux_run(["send-keys", "-t", pane_id, "Enter"])
        return rc == 0

    def send_keys(self, pane_id: str, keys: str, literal: bool = False) -> bool:
        """Send arbitrary key(s) to a tmux pane.

        If literal=True, uses -l flag to send raw text without interpretation.
        If literal=False, sends as tmux key name (Enter, Up, C-c, etc.).
        """
        cmd = ["send-keys", "-t", pane_id]
        if literal:
            cmd.append("-l")
        cmd.append(keys)
        rc, _ = self.tmux_run(cmd)
        return rc == 0

    def switch_to_pane(self, pane_id: str, prefer_companion: bool = False) -> bool:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return False
        # Cross-session: teleport via the shared primitive. `prefer_companion`
        # is intentionally ignored — companion lookup is an intra-session UX
        # affordance (the minimonitor lives in the same window as its agent).
        if (
            self.multi_session
            and pane.session_name
            and pane.session_name != self.session
        ):
            return switch_to_pane_anywhere(pane_id)
        # Same-session: existing companion-aware path.
        target_session = pane.session_name or self.session
        self.tmux_run([
            "select-window", "-t",
            tmux_window_target(target_session, pane.window_index),
        ])
        target_pane = pane_id
        if prefer_companion:
            companion = self.find_companion_pane_id(
                pane.window_index, target_session
            )
            if companion:
                target_pane = companion
        rc, _ = self.tmux_run(["select-pane", "-t", target_pane])
        return rc == 0

    def find_companion_pane_id(
        self, window_index: str, session: str | None = None
    ) -> str | None:
        """Find the minimonitor/companion pane ID in a given window."""
        target_session = session if session is not None else self.session
        fmt = "#{pane_id}\t#{pane_pid}"
        rc, stdout = self.tmux_run([
            "list-panes", "-t",
            tmux_window_target(target_session, window_index), "-F", fmt,
        ])
        if rc != 0:
            return None
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            pane_id_str, pid_str = parts
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            if _is_companion_process(pid):
                return pane_id_str
        return None

    def kill_pane(self, pane_id: str) -> bool:
        """Kill a tmux pane by its ID."""
        rc, _ = self.tmux_run(["kill-pane", "-t", pane_id])
        if rc == 0:
            self._pane_cache.pop(pane_id, None)
            self._last_content.pop(pane_id, None)
            self._last_change_time.pop(pane_id, None)
            return True
        return False

    def kill_window(self, pane_id: str) -> bool:
        """Kill the entire tmux window containing the given pane."""
        rc, _ = self.tmux_run(["kill-window", "-t", pane_id])
        if rc == 0:
            self._pane_cache.pop(pane_id, None)
            self._last_content.pop(pane_id, None)
            self._last_change_time.pop(pane_id, None)
            return True
        return False

    def kill_agent_pane_smart(self, pane_id: str) -> tuple[bool, bool]:
        """Kill an agent pane, collapsing the window if it was the last agent.

        Returns (ok, killed_window). If no other agent panes remain in the
        window after removing this one, the whole window is killed — which
        also cleans up any companion minimonitor pane. Otherwise only the
        requested pane is killed, preserving the minimonitor for surviving
        siblings.
        """
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return self.kill_pane(pane_id), False

        # Use the pane's own session so cross-session kills target the right
        # window; fall back to self.session for legacy single-session paths.
        target_session = pane.session_name or self.session
        window_target = tmux_window_target(target_session, pane.window_index)
        others = 0
        rc, stdout = self.tmux_run([
            "list-panes", "-t", window_target,
            "-F", "#{pane_id}\t#{pane_pid}",
        ])
        if rc != 0:
            return self.kill_pane(pane_id), False
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            other_id, pid_str = parts
            if other_id == pane_id:
                continue
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            if not _is_companion_process(pid):
                others += 1

        if others == 0:
            return self.kill_window(pane_id), True
        return self.kill_pane(pane_id), False

    def spawn_tui(self, tui_name: str) -> bool:
        rc, _ = self.tmux_run([
            "new-window", "-t", tmux_window_target(self.session, ""),
            "-n", tui_name, f"ait {tui_name}",
        ])
        return rc == 0

    def get_running_tuis(self) -> set[str]:
        return {
            pane.window_name
            for pane in self._pane_cache.values()
            if pane.category == PaneCategory.TUI
        }

    def get_missing_tuis(self) -> set[str]:
        return self.tui_names - self.get_running_tuis()


def load_monitor_config(project_root: Path) -> dict:
    """Load monitor config from project_config.yaml tmux.monitor section.

    Returns dict suitable for passing as kwargs to TmuxMonitor (minus session).
    """
    defaults = {
        "capture_lines": 200,
        "idle_threshold": 5.0,
        "agent_prefixes": list(DEFAULT_AGENT_PREFIXES),
        "tui_names": set(DEFAULT_TUI_NAMES),
        "compare_mode_default": DEFAULT_COMPARE_MODE,
    }
    config_path = project_root / "aitasks" / "metadata" / "project_config.yaml"
    if not config_path.is_file():
        return defaults
    try:
        import yaml
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        monitor = data.get("tmux", {}).get("monitor", {})
        if not isinstance(monitor, dict):
            return defaults
        if "capture_lines" in monitor:
            defaults["capture_lines"] = int(monitor["capture_lines"])
        if "idle_threshold_seconds" in monitor:
            defaults["idle_threshold"] = float(monitor["idle_threshold_seconds"])
        if "agent_window_prefixes" in monitor:
            defaults["agent_prefixes"] = list(monitor["agent_window_prefixes"])
        if "tui_window_names" in monitor:
            # Merge with registry defaults so new framework TUIs are never
            # masked by a stale override list in project_config.yaml.
            defaults["tui_names"] = set(TUI_NAMES) | set(monitor["tui_window_names"])
        if "compare_mode_default" in monitor:
            val = str(monitor["compare_mode_default"])
            if val in COMPARE_MODES:
                defaults["compare_mode_default"] = val
    except Exception:
        pass
    return defaults
