"""agent_launch_utils - Shared utilities for launching code agents from TUI screens.

Non-UI module (no Textual dependency). Provides terminal detection, agent command
resolution, and tmux session/window management.

Usage:
    from agent_launch_utils import (
        find_terminal, resolve_dry_run_command,
        is_tmux_available, get_tmux_sessions, get_tmux_windows,
        launch_in_tmux, load_tmux_defaults, TmuxLaunchConfig,
    )
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TmuxLaunchConfig:
    """Configuration for launching a command in tmux."""

    session: str
    window: str
    new_session: bool
    new_window: bool
    split_direction: str = "horizontal"  # only used when new_window=False


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
    project_root: Path, operation: str, *args: str
) -> str | None:
    """Resolve the full agent command via --dry-run.

    Calls aitask_codeagent.sh --dry-run invoke <operation> <args> and parses
    the DRY_RUN: <cmd> output. Returns the command string or None on failure.
    """
    wrapper = str(project_root / ".aitask-scripts" / "aitask_codeagent.sh")
    cmd = [wrapper, "--dry-run", "invoke", operation] + list(args)
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
            ["tmux", "list-windows", "-t", session, "-F", "#{window_index}:#{window_name}"],
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


def launch_in_tmux(command: str, config: TmuxLaunchConfig) -> subprocess.Popen:
    """Launch a command in tmux according to the given config.

    Returns the Popen object for the tmux command.
    """
    if config.new_session:
        # Create new session with a window, then switch to it
        tmux_cmd = [
            "tmux", "new-session", "-d",
            "-s", config.session, "-n", config.window,
            command,
        ]
        proc = subprocess.Popen(tmux_cmd)
        proc.wait()
        # Try to switch client (works if we're inside tmux)
        if os.environ.get("TMUX"):
            subprocess.Popen(["tmux", "switch-client", "-t", config.session])
        return proc
    elif config.new_window:
        tmux_cmd = [
            "tmux", "new-window", "-t", config.session,
            "-n", config.window,
            command,
        ]
        return subprocess.Popen(tmux_cmd)
    else:
        # Split existing window into a new pane
        split_flag = "-h" if config.split_direction == "horizontal" else "-v"
        target = f"{config.session}:{config.window}"
        tmux_cmd = [
            "tmux", "split-window", split_flag, "-t", target,
            command,
        ]
        return subprocess.Popen(tmux_cmd)


def load_tmux_defaults(project_root: Path) -> dict:
    """Load tmux defaults from project_config.yaml.

    Returns dict with keys: default_session, default_split, use_for_create.
    Falls back to hardcoded defaults if config is absent.
    """
    defaults = {
        "default_session": "aitasks",
        "default_split": "horizontal",
        "use_for_create": False,
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
            if "use_for_create" in tmux:
                defaults["use_for_create"] = bool(tmux["use_for_create"])
    except Exception:
        pass
    return defaults
