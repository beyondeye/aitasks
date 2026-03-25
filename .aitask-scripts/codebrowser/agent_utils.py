"""Shared utilities for launching code agents from TUI screens."""

import os
import shutil
import subprocess
from pathlib import Path


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


def resolve_agent_binary(
    project_root: Path, operation: str
) -> tuple[str | None, str | None, str | None]:
    """Resolve agent name and binary for an operation.

    Returns (agent_name, binary, error_msg).
    On success: agent_name and binary are set, error_msg is None.
    On failure: agent_name and binary are None, error_msg may describe the failure.
    """
    codeagent = project_root / ".aitask-scripts" / "aitask_codeagent.sh"
    if not codeagent.exists():
        return (None, None, None)
    try:
        result = subprocess.run(
            [str(codeagent), "resolve", operation],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_root),
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            error_msg = None
            if "unavailable" in stderr.lower():
                error_msg = stderr.split("ERROR:")[-1].strip() if "ERROR:" in stderr else stderr
            return (None, None, error_msg)
        info = {}
        for line in result.stdout.strip().splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                info[key] = val
        binary = info.get("BINARY", "")
        agent = info.get("AGENT", "unknown")
        return (agent, binary, None) if binary else (None, None, None)
    except (subprocess.TimeoutExpired, OSError):
        return (None, None, None)
