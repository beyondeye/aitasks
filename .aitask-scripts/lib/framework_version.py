"""framework_version - headless model layer for the syncer's version feature.

Pure functions over paths and strings: no Textual, no tmux calls. The syncer
TUI (t1223_3) wires the impure parts (window enumeration, spawning) around
these helpers, so the risky logic — shell-command construction, self-target
detection, active-target detection, handoff request — is unit-testable in
isolation.

Activity detection bound (Contract C of p1223): :func:`detect_target_activity`
only sees the window list of the target's tmux session that the CALLER
enumerated. An ``ait`` process running in an unrelated terminal, a detached
process, or another machine sharing the checkout is undetectable — that
residual is declared here, not silently implied to be covered. A ``busy`` /
``unknown`` result is a refuse-by-default signal; the explicit force-override
(destructive confirmation) lives in the UI layer, never here.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import tempfile
from pathlib import Path

# Version shape accepted by `ait upgrade` (aitask_upgrade.sh:83-89): the
# literal `latest` or a bare X.Y[.Z]. A leading `v` is deliberately NOT
# accepted here — callers strip it before validating.
VERSION_RE = r"^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$"
_NUMERIC_RE = r"^[0-9]+\.[0-9]+(\.[0-9]+)?$"

# Mirrors aitask_upgrade.sh:9 — the framework's canonical GitHub repo.
REPO = "beyondeye/aitasks"

# Mirrors the companion-pane defaults in agent_launch_utils (spawn gate).
COMPANION_PREFIXES = ("agent-", "create-")

_HELPER = Path(__file__).resolve().parent / "github_release.sh"


def read_installed_version(root: str | Path) -> str | None:
    """Read ``<root>/.aitask-scripts/VERSION``.

    Returns the version with surrounding whitespace and one leading ``v``
    stripped, or ``None`` when the file is missing, unreadable, or blank.
    Never raises.
    """
    try:
        text = (Path(root) / ".aitask-scripts" / "VERSION").read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    text = text.strip()
    if text.startswith("v"):
        text = text[1:].strip()
    return text or None


def resolve_latest_version(
    timeout: float = 10.0,
    *,
    helper: str | Path | None = None,
    repo: str = REPO,
) -> tuple[str | None, str | None]:
    """Resolve the latest published framework version.

    Shells out to ``github_resolve_latest_version`` from
    ``lib/github_release.sh`` (REST with git-tags fallback) rather than
    reimplementing release resolution. Returns ``(version, None)`` on
    success, ``(None, reason)`` on any failure — never raises.

    The subprocess runs in its own session (process group); on timeout the
    whole group is killed, covering the unbounded ``git ls-remote`` fallback
    the helper may have spawned (a plain child kill would orphan it).

    ``helper`` / ``repo`` are explicit test seams; production callers use the
    defaults (the module-adjacent script and the framework repo).
    """
    helper_path = str(helper) if helper is not None else str(_HELPER)
    cmd = [
        "bash", "-c",
        'source "$1" && github_resolve_latest_version "$2"',
        "bash", helper_path, repo,
    ]
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, start_new_session=True,
        )
    except (FileNotFoundError, OSError) as exc:
        return None, str(exc)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        proc.communicate()
        return None, "timeout after %gs" % timeout
    if proc.returncode != 0:
        err_lines = [ln.strip() for ln in (err or "").splitlines() if ln.strip()]
        reason = err_lines[-1] if err_lines else (
            "helper exited %d" % proc.returncode
        )
        return None, reason
    out_lines = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
    if not out_lines:
        return None, "no version in helper output"
    version = out_lines[-1]
    if version.startswith("v"):
        version = version[1:]
    if re.fullmatch(_NUMERIC_RE, version) is None:
        return None, "unparseable version: %r" % out_lines[-1]
    return version, None


def _parse_semver(value: str) -> tuple[int, ...] | None:
    try:
        return tuple(int(part) for part in str(value).split("."))
    except (TypeError, ValueError):
        return None


def version_status(installed: str | None, latest: str | None) -> str:
    """Compare two version strings.

    Returns ``'up_to_date'`` / ``'behind'`` / ``'ahead'`` (installed relative
    to latest), or ``'unknown'`` when either side is ``None`` or has a
    non-numeric component. ``1.2`` and ``1.2.0`` compare equal.
    """
    if installed is None or latest is None:
        return "unknown"
    left = _parse_semver(installed)
    right = _parse_semver(latest)
    if left is None or right is None:
        return "unknown"
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    if left == right:
        return "up_to_date"
    return "behind" if left < right else "ahead"


def is_self_target(root: str | Path, cwd: str | Path) -> bool:
    """Whether ``root`` is the repo this process is running from.

    ``os.path.realpath`` on BOTH sides, matching ``AitasksSession.key``
    semantics, so symlinked checkouts compare equal. Falls back to a plain
    string compare on ``OSError``.
    """
    try:
        return os.path.realpath(str(root)) == os.path.realpath(str(cwd))
    except OSError:
        return str(root) == str(cwd)


def detect_target_activity(
    session: str, windows: list[tuple[str, str]]
) -> str:
    """Classify a target session's windows as framework activity. PURE —
    the caller does the tmux enumeration (and short-circuits
    ``is_live=False`` sessions to idle without calling this).

    Returns one of:

    - ``'busy:<comma-separated window names>'`` — windows whose name is a
      registered framework TUI (``tui_registry.TUI_NAMES``) or starts with a
      companion/per-task prefix (``agent-``, ``create-``, ``brainstorm-``).
    - ``'idle'`` — no such window.
    - ``'unknown:tui-registry-unavailable'`` — the TUI-name registry could
      not be imported AND no prefix matched. Fail-closed: a classifier
      failure can widen refusal, never report a possibly-busy target idle.

    Only a literal ``'idle'`` permits an un-forced upgrade; consumers treat
    ``busy`` and ``unknown`` alike as refusal (force-override shows the
    reason).
    """
    try:
        from tui_registry import TUI_NAMES, BRAINSTORM_PREFIX
        busy_names: frozenset[str] = TUI_NAMES
        prefixes = COMPANION_PREFIXES + (BRAINSTORM_PREFIX,)
        registry_ok = True
    except Exception:
        busy_names = frozenset()
        prefixes = COMPANION_PREFIXES + ("brainstorm-",)
        registry_ok = False
    offending = [
        name for _index, name in windows
        if name in busy_names or name.startswith(prefixes)
    ]
    if offending:
        return "busy:" + ",".join(offending)
    if not registry_ok:
        return "unknown:tui-registry-unavailable"
    return "idle"


def build_upgrade_command(
    root: str | Path, version: str
) -> tuple[str, list[str]]:
    """Build the shell command for upgrading the repo at ``root``.

    The command is handed to tmux which runs it THROUGH A SHELL, so quoting
    is entirely our responsibility: ``version`` is validated against
    ``VERSION_RE`` before any interpolation (``ValueError`` otherwise) and
    the ``<root>/ait`` path is ``shlex.quote``d. The ``&&`` is load-bearing —
    a failed upgrade must not be followed by ``setup``.

    Returns ``(command_string, [quoted_ait_path, version])`` so tests can
    assert structure, not just text.
    """
    if not isinstance(version, str) or re.fullmatch(VERSION_RE, version) is None:
        raise ValueError("invalid version: %r" % (version,))
    quoted_ait = shlex.quote(str(Path(root) / "ait"))
    command = "%s upgrade %s && %s setup" % (quoted_ait, version, quoted_ait)
    return command, [quoted_ait, version]


def build_handoff_request(root: str | Path, version: str) -> dict:
    """Build the self-upgrade handoff request: data only, never a command.

    Exactly two keys — ``root`` (absolute) and ``version``. The shell
    wrapper that consumes it revalidates BOTH fields independently; the
    validation here is UX, not the security boundary.
    """
    if not isinstance(version, str) or re.fullmatch(VERSION_RE, version) is None:
        raise ValueError("invalid version: %r" % (version,))
    return {"root": os.path.abspath(str(root)), "version": version}


def write_handoff_request(path: str | Path, request: dict) -> None:
    """Atomically write ``request`` as JSON to ``path``.

    Temp file in the same directory + ``os.replace`` so the wrapper can
    never read a partially written request; the temp file is removed on any
    failure.
    """
    target = str(path)
    directory = os.path.dirname(target) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".handoff.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(request))
            fh.write("\n")
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
