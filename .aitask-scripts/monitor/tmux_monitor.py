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

import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PaneCategory(Enum):
    AGENT = "agent"
    TUI = "tui"
    OTHER = "other"


DEFAULT_AGENT_PREFIXES = ["agent-"]
DEFAULT_TUI_NAMES = {"board", "codebrowser", "settings", "brainstorm", "monitor", "minimonitor", "diffviewer"}

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


@dataclass
class PaneSnapshot:
    pane: TmuxPaneInfo
    content: str            # last N lines of captured text
    timestamp: float        # time.monotonic()
    idle_seconds: float     # seconds since last content change
    is_idle: bool           # idle_seconds > threshold (only meaningful for AGENT panes)


class TmuxMonitor:
    def __init__(
        self,
        session: str,
        capture_lines: int = 30,
        idle_threshold: float = 5.0,
        exclude_pane: str | None = None,
        agent_prefixes: list[str] | None = None,
        tui_names: set[str] | None = None,
    ):
        self.session = session
        self.capture_lines = capture_lines
        self.idle_threshold = idle_threshold
        self.exclude_pane = exclude_pane or os.environ.get("TMUX_PANE")
        self.agent_prefixes = agent_prefixes if agent_prefixes is not None else list(DEFAULT_AGENT_PREFIXES)
        self.tui_names = tui_names if tui_names is not None else set(DEFAULT_TUI_NAMES)

        self._last_content: dict[str, str] = {}
        self._last_change_time: dict[str, float] = {}
        self._pane_cache: dict[str, TmuxPaneInfo] = {}

    def classify_pane(self, window_name: str) -> PaneCategory:
        for prefix in self.agent_prefixes:
            if window_name.startswith(prefix):
                return PaneCategory.AGENT
        if window_name in self.tui_names:
            return PaneCategory.TUI
        if window_name.startswith("brainstorm-"):
            return PaneCategory.TUI
        return PaneCategory.OTHER

    def discover_panes(self) -> list[TmuxPaneInfo]:
        fmt = "\t".join([
            "#{window_index}", "#{window_name}", "#{pane_index}",
            "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
            "#{pane_width}", "#{pane_height}",
        ])
        try:
            result = subprocess.run(
                ["tmux", "list-panes", "-s", "-t", self.session, "-F", fmt],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return []
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

        panes: list[TmuxPaneInfo] = []
        for line in result.stdout.strip().splitlines():
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
            )
            panes.append(pane)
            self._pane_cache[pane_id] = pane
        return panes

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
        try:
            result = subprocess.run(
                ["tmux", "list-panes", "-t", window_id, "-F", fmt],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return []
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return []

        panes: list[TmuxPaneInfo] = []
        for line in result.stdout.strip().splitlines():
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
            )
            panes.append(pane)
        return panes

    def capture_pane(self, pane_id: str) -> PaneSnapshot | None:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return None
        try:
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-e", "-t", pane_id, "-S", f"-{self.capture_lines}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                return None
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

        now = time.monotonic()
        content = result.stdout

        prev_content = self._last_content.get(pane_id)
        if prev_content is None or content != prev_content:
            self._last_content[pane_id] = content
            self._last_change_time[pane_id] = now

        last_change = self._last_change_time.get(pane_id, now)
        idle_seconds = now - last_change
        is_idle = idle_seconds > self.idle_threshold if pane.category == PaneCategory.AGENT else False

        return PaneSnapshot(
            pane=pane,
            content=content,
            timestamp=now,
            idle_seconds=idle_seconds,
            is_idle=is_idle,
        )

    def capture_all(self) -> dict[str, PaneSnapshot]:
        panes = self.discover_panes()
        current_ids = {p.pane_id for p in panes}

        # Clean stale entries
        stale = [pid for pid in self._last_content if pid not in current_ids]
        for pid in stale:
            del self._last_content[pid]
            self._last_change_time.pop(pid, None)
            self._pane_cache.pop(pid, None)

        snapshots: dict[str, PaneSnapshot] = {}
        for pane in panes:
            snap = self.capture_pane(pane.pane_id)
            if snap is not None:
                snapshots[pane.pane_id] = snap
        return snapshots

    def send_enter(self, pane_id: str) -> bool:
        try:
            result = subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "Enter"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def send_keys(self, pane_id: str, keys: str, literal: bool = False) -> bool:
        """Send arbitrary key(s) to a tmux pane.

        If literal=True, uses -l flag to send raw text without interpretation.
        If literal=False, sends as tmux key name (Enter, Up, C-c, etc.).
        """
        try:
            cmd = ["tmux", "send-keys", "-t", pane_id]
            if literal:
                cmd.append("-l")
            cmd.append(keys)
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def switch_to_pane(self, pane_id: str) -> bool:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return False
        try:
            # Select window first, then pane
            subprocess.run(
                ["tmux", "select-window", "-t", f"{self.session}:{pane.window_index}"],
                capture_output=True, timeout=5,
            )
            result = subprocess.run(
                ["tmux", "select-pane", "-t", pane_id],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def kill_pane(self, pane_id: str) -> bool:
        """Kill a tmux pane by its ID."""
        try:
            result = subprocess.run(
                ["tmux", "kill-pane", "-t", pane_id],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                self._pane_cache.pop(pane_id, None)
                self._last_content.pop(pane_id, None)
                self._last_change_time.pop(pane_id, None)
                return True
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def spawn_tui(self, tui_name: str) -> bool:
        try:
            result = subprocess.run(
                ["tmux", "new-window", "-t", f"{self.session}:", "-n", tui_name, f"ait {tui_name}"],
                capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

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
        "capture_lines": 30,
        "idle_threshold": 5.0,
        "agent_prefixes": list(DEFAULT_AGENT_PREFIXES),
        "tui_names": set(DEFAULT_TUI_NAMES),
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
            defaults["tui_names"] = set(monitor["tui_window_names"])
    except Exception:
        pass
    return defaults
