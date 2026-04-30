"""desync_summary — shared compact desync formatter for monitor / minimonitor.

Invokes ``desync_state.py snapshot --format lines`` as a subprocess against a
project root, parses the line-protocol output, and returns a short string
suitable for appending to a session-bar label. A 30s in-process TTL cache
prevents repeated invocations on every refresh tick.

Returns an empty string when both refs are clean (so callers can append it
unconditionally) and a markup-styled string when at least one ref is behind.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

_TTL_SECONDS = 30
_HELPER = Path(__file__).resolve().parent.parent / "lib" / "desync_state.py"
_cache: dict[str, tuple[float, str, str]] = {}


def get_desync_summary(project_root: Path, *, compact: bool = False) -> str:
    """Return a short desync summary or empty string when clean.

    ``compact=True`` produces an ultra-short suffix (≤10 chars, e.g.
    ``↓3``) suitable for the minimonitor's narrow bar. ``compact=False``
    produces the longer monitor variant (``desync: aitask-data 3↓``).
    """
    key = str(project_root)
    variant = "compact" if compact else "full"
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and cached[2] == variant and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]
    result = _fetch(project_root, compact=compact)
    _cache[key] = (now, result, variant)
    return result


def _fetch(project_root: Path, *, compact: bool) -> str:
    if not _HELPER.is_file():
        return ""
    try:
        proc = subprocess.run(
            [sys.executable, str(_HELPER), "snapshot", "--format", "lines"],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=2,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return _format(proc.stdout, compact=compact)


def _format(lines_output: str, *, compact: bool) -> str:
    refs: list[tuple[str, str, int, int]] = []
    cur_name: str | None = None
    cur_status: str = "ok"
    cur_ahead: int = 0
    cur_behind: int = 0
    for raw in lines_output.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if key == "REF":
            if cur_name is not None:
                refs.append((cur_name, cur_status, cur_ahead, cur_behind))
            cur_name = val
            cur_status = "ok"
            cur_ahead = 0
            cur_behind = 0
        elif key == "STATUS":
            cur_status = val
        elif key == "AHEAD":
            try:
                cur_ahead = int(val)
            except ValueError:
                cur_ahead = 0
        elif key == "BEHIND":
            try:
                cur_behind = int(val)
            except ValueError:
                cur_behind = 0
    if cur_name is not None:
        refs.append((cur_name, cur_status, cur_ahead, cur_behind))

    if compact:
        worst = 0
        for _name, status, _ahead, behind in refs:
            if status != "ok":
                continue
            if behind > worst:
                worst = behind
        return f" · [yellow]↓{worst}[/]" if worst > 0 else ""

    parts: list[str] = []
    for name, status, _ahead, behind in refs:
        if status != "ok":
            continue
        if behind > 0:
            parts.append(f"{name} {behind}↓")
    if not parts:
        return ""
    return " · [yellow]desync: " + ", ".join(parts) + "[/]"
