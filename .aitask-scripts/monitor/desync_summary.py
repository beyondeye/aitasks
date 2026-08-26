"""desync_summary — shared desync formatter for monitor / minimonitor.

Invokes ``desync_state.py snapshot --format lines`` as a subprocess against a
project root, parses the line-protocol output, and returns a short string
suitable for appending to a session-bar label. A 30s in-process TTL cache
prevents repeated invocations on every refresh tick.

Returns an empty string when both refs are clean (so callers can append it
unconditionally) and a markup-styled string when at least one ref is behind.

**Three readers over one cache, with different blocking contracts (t1622).**
The probe costs a fresh Python interpreter, so *which* reader a call site picks
is a correctness question, not a style one:

* :func:`get_desync_summary_async` — fetches, off the event loop. **Any Textual
  path uses this**, awaited from a worker or a timer coroutine.
* :func:`get_desync_summary_cached` — never spawns; returns whatever the last
  fetch stored. For synchronous call sites that must not block, e.g. a keypress
  handler rebuilding a session bar.
* :func:`get_desync_summary` — the synchronous fetcher. Only for callers that
  own their own thread and can afford to block in it. It is deliberately not
  imported by either TUI any more.
"""
from __future__ import annotations

import asyncio
import contextlib
import subprocess
import sys
import time
from pathlib import Path

_TTL_SECONDS = 30
#: Wall-clock cap on one helper invocation, shared by both fetchers so the sync
#: and async paths cannot drift apart.
_TIMEOUT_SECONDS = 2
_HELPER = Path(__file__).resolve().parent.parent / "lib" / "desync_state.py"
_cache: dict[str, tuple[float, str, str]] = {}


def _variant(compact: bool) -> str:
    return "compact" if compact else "full"


def get_desync_summary(project_root: Path, *, compact: bool = False) -> str:
    """Return a short desync summary or empty string when clean.

    ``compact=True`` produces an ultra-short suffix (≤10 chars, e.g.
    ``↓3``) suitable for the minimonitor's narrow bar. ``compact=False``
    produces the longer monitor variant (``desync: aitask-data 3↓``).

    **Blocks the calling thread** for up to :data:`_TIMEOUT_SECONDS` on a cache
    miss. Never call it from a Textual path — use
    :func:`get_desync_summary_async` or :func:`get_desync_summary_cached`.
    """
    key = str(project_root)
    variant = _variant(compact)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and cached[2] == variant and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]
    result = _fetch(project_root, compact=compact)
    _cache[key] = (now, result, variant)
    return result


async def get_desync_summary_async(project_root: Path, *, compact: bool = False) -> str:
    """Async sibling of :func:`get_desync_summary` — same cache, same contract.

    The reader every Textual call site wants: on a cache miss the sync version
    ran a fresh Python interpreter inline on whatever was calling it, which on
    the monitor's refresh tick meant the render path (t1622).
    """
    key = str(project_root)
    variant = _variant(compact)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and cached[2] == variant and (now - cached[0]) < _TTL_SECONDS:
        return cached[1]
    result = await _fetch_async(project_root, compact=compact)
    _cache[key] = (now, result, variant)
    return result


def get_desync_summary_cached(project_root: Path, *, compact: bool = False) -> str:
    """The last summary computed for ``project_root``, or ``""`` — never spawns.

    For synchronous call sites that must not block: a keypress handler that
    rebuilds a session bar has no summary of its own to compute and no business
    starting a subprocess to get one.

    **Ignores the TTL on purpose.** The TTL decides when to RE-FETCH, which only
    the two fetching readers can do; expiring the value here as well would blank
    a still-true desync warning the moment the user pressed a key, and repaint it
    one tick later. A refreshing caller keeps this entry within one TTL of the
    truth. An entry recorded under the other ``variant`` is not reusable and
    yields ``""``.
    """
    cached = _cache.get(str(project_root))
    if not cached:
        return ""
    return cached[1] if cached[2] == _variant(compact) else ""


def _fetch(project_root: Path, *, compact: bool) -> str:
    if not _HELPER.is_file():
        return ""
    try:
        proc = subprocess.run(
            [sys.executable, str(_HELPER), "snapshot", "--format", "lines"],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0:
        return ""
    return _format(proc.stdout, compact=compact)


async def _terminate(proc) -> None:
    """SIGKILL and reap. Called from BOTH the timeout and the cancel path."""
    with contextlib.suppress(ProcessLookupError):
        proc.kill()
    with contextlib.suppress(Exception):
        await proc.wait()


async def _fetch_async(project_root: Path, *, compact: bool) -> str:
    if not _HELPER.is_file():
        return ""
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, str(_HELPER), "snapshot", "--format", "lines",
            cwd=str(project_root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except (FileNotFoundError, OSError):
        return ""
    try:
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        await _terminate(proc)
        return ""
    except asyncio.CancelledError:
        # Cancellation is a SECOND exit, not a variant of the timeout:
        # `wait_for` cancels the inner `communicate()` and re-raises without
        # touching the child, and Textual cancels the refresh worker when the
        # app exits — so catching only TimeoutError leaks a live Python
        # interpreter past the TUI it belonged to. Kill BEFORE the re-raise and
        # never swallow the CancelledError: `kill()` is synchronous, so the
        # signal lands even if the reaping `await` is cancelled in turn, and by
        # then the child is already dying.
        await _terminate(proc)
        raise
    if proc.returncode != 0:
        return ""
    return _format(stdout_bytes.decode("utf-8", errors="replace"), compact=compact)


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
