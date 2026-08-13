"""monitor_core - Headless core for the monitor pipeline (no Textual).

The non-UI half of `ait monitor` / `ait minimonitor`: tmux pane discovery,
content capture, idle/awaiting-input detection, pane categorization, the
persistent `tmux -C` control-mode client, and the task-metadata cache. Shared
by both Textual TUIs and the future `ait applink` WebSocket listener — so it
carries **no Textual / rich imports**.

tmux execution is delegated to the gateway `lib/tmux_exec.py`
(`TmuxClient.run_via_control` / `run_async_via_control`); this module does not
re-own the control-client-vs-subprocess dispatch (t952_3).

Extracted from `tmux_monitor.py`, `tmux_control.py`, and `monitor_shared.py`
in t822_6; those modules now re-export from here for backwards compatibility.
"""
from __future__ import annotations

import asyncio
import collections
import contextlib
import enum
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import NamedTuple, Optional

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
# `lib/` holds the gateway + launch/registry helpers and task_yaml (the
# frontmatter parser used by TaskInfoCache, moved there in t1217).
for _extra_path in (_SCRIPTS_DIR / "lib",):
    if str(_extra_path) not in sys.path:
        sys.path.insert(0, str(_extra_path))
from tui_registry import BRAINSTORM_PREFIX, TUI_NAMES  # noqa: E402
from tmux_exec import TmuxClient, tmux_socket_args  # noqa: E402  (gateway: exec-strategy dispatch + socket flag)
from agent_launch_utils import (  # noqa: E402
    AitasksSession,
    TmuxLaunchConfig,
    attach_companion_cleanup_hook,
    discover_aitasks_sessions,
    discover_aitasks_sessions_async,
    launch_in_tmux,
    resolve_pane_id_by_pid,
    switch_to_pane_anywhere,
    tmux_session_target,
    tmux_window_target,
)
from followup_kinds import normalize_followup_kind  # noqa: E402
from task_yaml import parse_frontmatter  # noqa: E402
import gate_ledger  # noqa: E402  (shared gate-ledger parser; single derivation path)
import workflow_phase  # noqa: E402  (advisory phase seam, t1420 — never a gate)

try:
    from .prompt_patterns import (
        AGENT_KEYS,
        PromptPattern,
        agent_key_from_pane,
        all_patterns,
        scope_patterns,
    )
    from .ansi_utils import strip_ansi
    from .concern_parser import (
        contains_block_evidence,
        parse_block_meta,
        parse_reviewed_at_epoch,
    )
except ImportError:  # imported top-level (tests put MONITOR_DIR on PYTHONPATH)
    from prompt_patterns import (  # noqa: E402
        AGENT_KEYS,
        PromptPattern,
        agent_key_from_pane,
        all_patterns,
        scope_patterns,
    )
    from ansi_utils import strip_ansi  # noqa: E402
    from concern_parser import (  # noqa: E402
        contains_block_evidence,
        parse_block_meta,
        parse_reviewed_at_epoch,
    )


# Abstract key name → tmux send-keys argument (for special keys). Lives here in
# the headless core (not monitor_app) so both the desktop preview-zone key
# forwarding and the applink `forward_key` verb translate identically
# server-side (t822_7). monitor_app re-exports this name for back-compat.
_TEXTUAL_TO_TMUX = {
    "enter": "Enter",
    "escape": "Escape",
    "backspace": "BSpace",
    "up": "Up",
    "down": "Down",
    "left": "Left",
    "right": "Right",
    "space": "Space",
    "delete": "DC",
    "home": "Home",
    "end": "End",
    "pageup": "PPage",
    "pagedown": "NPage",
    "insert": "IC",
    "f1": "F1",
    "f2": "F2",
    "f3": "F3",
    "f4": "F4",
    "f5": "F5",
    "f6": "F6",
    "f7": "F7",
    "f8": "F8",
    "f9": "F9",
    "f10": "F10",
    "f11": "F11",
    "f12": "F12",
}


def translate_key(key: str, character: str | None = None) -> tuple[str, bool] | None:
    """Translate an abstract key name into tmux ``send-keys`` arguments.

    Returns ``(keys, literal)`` suitable for :meth:`TmuxMonitor.send_keys`, or
    ``None`` when the key cannot be mapped. Shared by the desktop key-forward
    path (``monitor_app._forward_key_to_tmux``) and the applink ``forward_key``
    verb so both sides resolve keys identically:

      * special keys (``up``, ``escape``, ``f5`` …) → the tmux key name, non-literal
      * ``ctrl+x`` → ``C-x``, non-literal
      * a single printable character → sent literally

    ``character`` is the desktop ``event.character`` (the resolved glyph for
    keys whose abstract name is not itself the character, e.g. ``!`` arrives as
    ``exclamation_mark``); mobile clients pass only ``key`` (the literal glyph
    for plain characters) and leave ``character`` as ``None``.
    """
    if key in _TEXTUAL_TO_TMUX:
        return _TEXTUAL_TO_TMUX[key], False
    if key.startswith("ctrl+"):
        return f"C-{key[5:]}", False
    if character and len(character) == 1:
        return character, True
    if len(key) == 1:
        return key, True
    return None


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

# CSI escape stripping (`strip_ansi`) lives in `monitor/ansi_utils.py` — a pure,
# dependency-free module so `concern_parser` can share this exact implementation
# without importing this module's asyncio / subprocess / gateway graph (t1216_1).
_PROMPT_DETECTION_TAIL_LINES = 6


def _prompt_detection_text(s: str) -> str:
    """Return the live bottom slice used for awaiting-input prompt matching."""
    lines = s.splitlines()
    if len(lines) <= _PROMPT_DETECTION_TAIL_LINES:
        return s
    return "\n".join(lines[-_PROMPT_DETECTION_TAIL_LINES:])


@dataclass
class ClassifyResult:
    """Pure result of off-loop content classification for one pane (t1111_4).

    Carries only plain data so it can cross the ``asyncio.to_thread`` boundary.
    Holds no ``TmuxMonitor`` state; the loop-side commit
    (:meth:`TmuxMonitor.commit_snapshots`) turns it into the durable
    ``_last_content`` / ``_last_change_time`` bookkeeping and a ``PaneSnapshot``.
    """
    compare_value: str
    awaiting_input: bool = False
    awaiting_input_kind: str = ""
    # Resolution provenance (t1467). `scoped` is False whenever matching was NOT
    # narrowed to a known agent — an unresolvable pane command, or a caller that
    # passed no agent. False is the honest default: a result built by the
    # fail-closed `except` path was not scoped and must not read as though it
    # were. Consumers use these to tell the two regimes apart.
    agent_key: str = ""
    scoped: bool = False


def classify_content(
    content: str,
    mode: str,
    prompt_patterns: list[PromptPattern],
    category: PaneCategory,
    agent: str = "",
) -> ClassifyResult:
    """Pure, module-level CPU work extracted from ``_finalize_capture`` (t1111_4).

    Runs the ANSI strip (for the compare value) and the awaiting-input prompt
    scan — the per-agent, per-tick regex work that used to run on the Textual
    event loop. No ``self``, no shared-dict mutation, no widget access, so it is
    safe to batch off-loop via ``asyncio.to_thread``. ``prompt_patterns`` is read
    only. All ``_last_content`` / ``_last_change_time`` mutation stays loop-side.

    Since t1467 matching is **scoped to the pane's own agent**: ``agent`` is a
    resolved key from ``lib/agent_keys.agent_key_from_pane``, and patterns owned
    by a different agent are dropped (``prompt_patterns.scope_patterns``). The
    default ``""`` preserves the pre-t1467 flat-list behaviour, which is also
    what an unresolvable pane command gets — so no caller is broken and no
    working detection is lost.

    The result carries the resolution outcome (``agent_key`` / ``scoped``) so
    that "matched under scoped rules" and "matched from the unscoped flat list"
    are distinguishable downstream instead of looking identical.
    """
    compare_value = strip_ansi(content) if mode == COMPARE_MODE_STRIPPED else content
    agent_key = (agent or "").strip().lower()
    scoped = agent_key in AGENT_KEYS
    awaiting_input = False
    awaiting_input_kind = ""
    if category == PaneCategory.AGENT and prompt_patterns:
        stripped_text = compare_value if mode == COMPARE_MODE_STRIPPED else strip_ansi(content)
        prompt_text = _prompt_detection_text(stripped_text)
        for p in scope_patterns(prompt_patterns, agent_key):
            if p.regex.search(prompt_text):
                awaiting_input = True
                awaiting_input_kind = p.name
                break
    return ClassifyResult(
        compare_value=compare_value,
        awaiting_input=awaiting_input,
        awaiting_input_kind=awaiting_input_kind,
        agent_key=agent_key if scoped else "",
        scoped=scoped,
    )


def _classify_one(
    content: str,
    mode: str,
    prompt_patterns: list[PromptPattern],
    category: PaneCategory,
    agent: str = "",
) -> ClassifyResult:
    """Fail-closed single-pane classify (invariant D): a raising regex/strip
    degrades to raw content (never awaiting) so one bad pane never propagates."""
    try:
        return classify_content(content, mode, prompt_patterns, category, agent)
    except Exception:
        return ClassifyResult(compare_value=content)


def _classify_batch(
    items: list[tuple["TmuxPaneInfo", str, str]],
    prompt_patterns: list[PromptPattern],
) -> list[tuple["TmuxPaneInfo", str, ClassifyResult]]:
    """Off-loop batch of :func:`classify_content`, fail-closed per pane (t1111_4).

    ``items`` are ``(pane, content, mode)`` tuples read on the loop before the
    hop. Runs inside a single ``asyncio.to_thread`` call; wrapping each pane
    individually (via :func:`_classify_one`) means one malformed pane degrades to
    raw content instead of dropping the whole refresh (invariant E: one batch per
    cycle, not per-pane fan-out).
    """
    return [
        (pane, content, _classify_one(content, mode, prompt_patterns, pane.category,
                                      agent_key_from_pane(pane.current_command,
                                                          pane.pane_pid,
                                                          pane.pane_id)))
        for pane, content, mode in items
    ]


_COMPANION_KEYWORDS = ("minimonitor", "monitor_app")

# TTL for a memoized *positive* companion verdict (see
# `TmuxMonitor._is_companion_pane`). Negative verdicts are never memoized, so
# this bounds nothing user-visible — it exists purely so no verdict can be
# cached for the lifetime of the process.
_COMPANION_MEMO_TTL = 300.0


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


# -- Shadow companion panes (t986) --------------------------------------------
#
# A "shadow" is a second coding-agent CLI spawned in (by default) the same tmux
# window as the agent it follows. Because splitting a window does not rename it,
# a same-window shadow shares the *agent's* window name — so it cannot be told
# apart by window name. Instead the spawner (t986_5) records the shadowed
# agent's pane id in the pane-scoped tmux user option below. A pane carrying a
# non-empty value is a shadow *helper*: excluded from agent lists exactly like
# the minimonitor/monitor companion panes, and never resolved to a task. The
# value also drives lifecycle cleanup — when the shadowed agent's pane dies,
# `aitask_companion_cleanup.sh` kills the bound shadow.
SHADOW_TARGET_OPTION = "@aitask_shadow_target"

# Pane-scoped user-option a shadow stamps with the wall-clock epoch at which it
# last read its followed agent (t1104). minimonitor compares it against when the
# followed pane last changed to tell whether the shadow's feedback is still
# current. A timestamp (not a content hash) is used because an exact snapshot
# hash of a live terminal is too brittle. Set by aitask_shadow_capture.sh.
SHADOW_ANALYZED_AT_OPTION = "@aitask_shadow_analyzed_at"

# Pane-scoped user-option carrying the ADVISORY workflow-phase signal for the
# followed agent (t1420), in ``workflow_phase.format_signal`` form. Written on
# the SHADOW pane at spawn and re-stamped every tick by
# :func:`refresh_shadow_phase_stamp`, so the shadow reads a value that is current
# at every refetch rather than frozen at spawn — the property argv could not
# offer. Advisory only: nothing may refuse an action because of what it holds.
SHADOW_PHASE_OPTION = "@aitask_shadow_phase"


def is_shadow_target(shadow_target: str) -> bool:
    """True when a pane's ``@aitask_shadow_target`` value marks it a shadow.

    Pure: takes the already-read option value (empty/whitespace ⇒ not a
    shadow), so the tmux read stays at the call site and this stays
    unit-testable.
    """
    return bool(shadow_target.strip())


def _pane_id_num(pane_id: str) -> int:
    """Numeric sort key for a tmux pane id (``%7`` → 7); malformed → -1.

    tmux assigns pane ids monotonically, so the largest number is the most
    recently created pane. Used to pick the newest shadow deterministically
    when more than one targets the same followed pane (an orphan that escaped
    cleanup) — including by :func:`match_shadow_pane`, which used to carry its
    own identical copy of this body in minimonitor (t1133, collapsed in t1216_1).
    """
    try:
        return int(pane_id.lstrip("%"))
    except (ValueError, AttributeError):
        return -1


def match_shadow_pane_info(
    list_output: str, followed_pane_id: str
) -> tuple[str, str] | None:
    """Resolve the shadow pane bound to ``followed_pane_id`` plus its command.

    Pure (no tmux): ``list_output`` is :func:`shadow_query_args` text —
    ``#{pane_id}\t#{@aitask_shadow_target}\t#{pane_current_command}``. Returns
    ``(pane_id, current_command)`` for the pane whose ``@aitask_shadow_target``
    equals ``followed_pane_id`` (the shadow pane carries the followed pane's id
    — see ``shadow_agent.md``), or ``None``. An empty target marks a non-shadow
    pane and is ignored (``is_shadow_target``). A two-field line (older format
    / test stubs) still resolves the pane, with command ``""`` — the review
    loop reads that as an unknown shadow agent and refuses/disarms rather than
    guessing (t1159_2).

    Defense-in-depth: if more than one pane matches (an orphaned live shadow
    that escaped cleanup — the launch guard in ``action_launch_shadow``
    normally prevents this), return the **newest** (largest ``%N``)
    deterministically. The caller may notify when ``> 1`` match is seen.
    """
    matches: list[tuple[str, str]] = []
    for line in list_output.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        pane_id, target = parts[0].strip(), parts[1].strip()
        command = parts[2].strip() if len(parts) > 2 else ""
        if not is_shadow_target(target):
            continue
        if target == followed_pane_id:
            matches.append((pane_id, command))
    if not matches:
        return None
    return max(matches, key=lambda m: _pane_id_num(m[0]))


def match_shadow_pane(list_output: str, followed_pane_id: str) -> str | None:
    """Pane-id-only view of :func:`match_shadow_pane_info`.

    Implemented on top of it so the two selection rules can never drift.
    """
    info = match_shadow_pane_info(list_output, followed_pane_id)
    return info[0] if info else None


# Hard ceiling for the shadow-pane tmux query + capture shell-out (seconds).
# Keeps the picker hotkey and the refresh-tick auto-offer from ever blocking the
# Textual event loop on a stalled tmux / helper (t1037_4).
_SHADOW_CAPTURE_TIMEOUT = 3.0

# One-shot deeper window for the EXPLICIT concern-picker hotkey when the default
# plan-review depth still clipped the block's opening fence (t1187). Only the
# user-initiated 'c' path pays for it, and only once per press — the per-tick
# auto-offer never retries.
_SHADOW_DEEP_RETRY_LINES = 1500

# Shown when a concern block is present but its opening fence fell outside the
# capture window. Distinguishes a too-shallow capture from a genuinely
# concern-free shadow, which used to read identically ("no concerns") — the
# silent false negative behind t1187.
_SHADOW_TRUNCATED_MSG = (
    "Shadow's concern block is cut off above the capture window "
    "— increase SHADOW_PLAN_CAPTURE_LINES"
)


def shadow_query_args() -> list[str]:
    """tmux argv listing every pane's id + @aitask_shadow_target + command.

    Shared by the sync and async reverse-lookups so the format never drifts.
    The third field feeds the review loop's shadow-agent resolution
    (:func:`match_shadow_pane_info`) at zero extra tmux round trips; two-field
    parsers keep working (they read fields 0-1 only).
    """
    return ["list-panes", "-a", "-F",
            f"#{{pane_id}}\t#{{{SHADOW_TARGET_OPTION}}}\t"
            "#{pane_current_command}"]


def find_shadow_pane_status(
    monitor, followed_pane_id: str
) -> tuple[bool, str | None]:
    """Sync reverse lookup that discriminates query failure from "no shadow".

    Returns ``(ok, pane)``. ``ok`` is False when the query itself could not be
    answered (no monitor, or ``list-panes`` returned non-zero) — distinct from
    ``(True, None)``, which is a verified "this agent has no shadow".

    :func:`find_shadow_pane` collapses both into ``None``, which is right for the
    six *readers* (preview, key forwarding, concern picker) where a failed lookup
    and an absent shadow are equally "nothing to show". It is wrong for a
    **create** decision: an unverifiable state must not be read as permission to
    spawn a second shadow, so the launch guards use this primitive and refuse on
    ``ok is False`` (t1216_4).

    ``monitor`` is duck-typed on the **gateway surface only** (``tmux_run`` ->
    ``(rc, stdout)``), not on ``TmuxMonitor``: the sole thing needed is one
    ``list-panes`` round-trip, and keeping the contract that narrow lets both
    apps — and the test stubs — pass whatever they already hold (t1216_1).
    """
    if monitor is None:
        return False, None
    rc, out = monitor.tmux_run(shadow_query_args(), timeout=2)
    if rc != 0:
        return False, None
    return True, match_shadow_pane(out, followed_pane_id)


def find_shadow_pane(monitor, followed_pane_id: str) -> str | None:
    """Sync reverse lookup of the shadow pane bound to ``followed_pane_id``.

    Fail-open view of :func:`find_shadow_pane_status` for readers: a failed query
    and a verified absence both read as ``None``. Do **not** use it to gate a
    spawn — see that function's note.

    The picker action and the refresh-tick auto-offer use
    :func:`find_shadow_pane_async` so they never block the event loop.
    """
    ok, pane = find_shadow_pane_status(monitor, followed_pane_id)
    return pane if ok else None


async def find_shadow_pane_async(monitor, followed_pane_id: str) -> str | None:
    """Async (event-loop safe) reverse lookup for the picker / auto-offer."""
    _ok, pane, _command = await find_shadow_pane_info_async(
        monitor, followed_pane_id
    )
    return pane


async def find_shadow_pane_info_async(
    monitor, followed_pane_id: str
) -> tuple[bool, str | None, str]:
    """Async reverse lookup with a success discriminator and the shadow's
    command: ``(ok, pane, current_command)``.

    ``ok`` is False when the query itself could not be answered (no monitor,
    nonzero rc, timeout) — distinct from ``(True, None, "")``, a verified
    "this agent has no shadow". The review loop is a *decision* consumer
    (auto-disarm destroys the user's armed state), so like the launch guards
    (t1216_4) it must not consume the fail-open collapsed view: a transient
    tmux failure pauses the loop, only a verified absence disarms it
    (t1159_2). Readers keep using :func:`find_shadow_pane_async`.
    """
    if monitor is None:
        return False, None, ""
    rc, out = await monitor.tmux_run_async(
        shadow_query_args(), timeout=_SHADOW_CAPTURE_TIMEOUT
    )
    if rc != 0:
        return False, None, ""
    info = match_shadow_pane_info(out, followed_pane_id)
    if info is None:
        return True, None, ""
    return True, info[0], info[1]


async def capture_raw_tail(
    monitor, pane_id: str, *, lines: int = 15
) -> str | None:
    """Raw (ANSI-carrying) tail of a pane via the gateway; ``None`` on failure.

    The review loop's shadow-readiness detector (t1159_2) must see raw
    styling: Claude Code renders its composer *placeholder hint* as dim text
    that ANSI-stripping makes indistinguishable from typed text, so the
    cleaned :func:`capture_shadow_text` path cannot answer "is the composer
    empty". Deliberately tiny (default 15 lines) — it reads the prompt area,
    not the transcript — and paid only while a loop is armed.
    """
    if monitor is None:
        return None
    rc, out = await monitor.tmux_run_async(
        ["capture-pane", "-p", "-e", "-t", pane_id, "-S", f"-{lines}"],
        timeout=_SHADOW_CAPTURE_TIMEOUT,
    )
    if rc != 0:
        return None
    return out


async def capture_shadow_text(
    shadow_pane: str, *, lines: int | None = None
) -> str | None:
    """Capture a shadow pane as clean, wrap-joined text, or ``None`` on failure.

    Reuses ``aitask_shadow_capture.sh`` (the shadow skill's own capture path,
    ``-J``-joined per the parser's capture-join contract) so cleaning never
    diverges. Async with a hard timeout: a stalled tmux / helper degrades to
    ``None`` rather than hanging the UI (t1037_4).

    Module-level and monitor-free by design: the body touches no instance state,
    so neither app needs a ``TmuxMonitor`` to read a shadow pane (t1216_1).

    Always passes ``--deep``: what we are reading here IS plan-review output
    (the shadow's concern list plus its fully-framed machine block), which is
    exactly why the plan sub-procedures use that depth. At the narrow widths
    a shadow pane runs at, the 200-line default can start *inside* the block
    and clip its opening fence — which both parser entry points report as
    "no concerns" (t1187).

    ``lines`` overrides the deep depth for one call (``SHADOW_PLAN_CAPTURE_
    LINES``), used by the explicit picker hotkey's single deeper retry.

    Note this deliberately does NOT go through the tmux gateway: the ``-J``
    wrap-join lives in ``aitask_shadow_capture.sh`` and is the parser's
    contract, whereas the tick capture (:meth:`TmuxMonitor._capture_args`) is
    ``-p -e`` with no ``-J``. The two captures cannot be served from one call.
    """
    script = _SCRIPTS_DIR / "aitask_shadow_capture.sh"
    env = None
    if lines is not None:
        env = dict(os.environ, SHADOW_PLAN_CAPTURE_LINES=str(lines))
    try:
        proc = await asyncio.create_subprocess_exec(
            # ``--any-pane`` is the ONE sanctioned opt-out of the helper's
            # wrong-pane refusal (t1319), for two independent reasons. (1) That
            # guard exists to catch a pane id a *model* transcribed and may have
            # truncated; ``shadow_pane`` here comes from ``find_shadow_pane``, so
            # there is nothing for it to protect. (2) A TUI run from the user's
            # personal tmux while the framework lives on ``-L ait`` is a
            # cross-server caller, which the helper refuses — and because this
            # call sends stderr to DEVNULL and returns None on a non-zero exit,
            # that refusal would surface as a silent "no concerns" in the picker.
            # Do not copy this flag to callers whose pane id is model-supplied.
            str(script), "--deep", "--any-pane", shadow_pane,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
    except OSError:
        return None
    try:
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=_SHADOW_CAPTURE_TIMEOUT
        )
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        return None
    if proc.returncode:
        return None
    return stdout_bytes.decode("utf-8", errors="replace")


async def compute_shadow_staleness(
    monitor, shadow_pane: str, followed_pane: str, eps: float
) -> tuple[bool | None, float | None]:
    """Is the shadow's feedback stale relative to the followed agent? (t1104)

    Compares *times*, not content: the shadow stamps when it last read the
    followed pane (``@aitask_shadow_analyzed_at``, epoch); if the followed pane
    changed after that (per this module's change detection), the shadow has not
    seen the newer output => stale. Robust to a live TUI settling by a character
    (which an exact snapshot hash mis-reads as stale).

    Returns ``(stale, analyzed_at)`` where ``stale`` is a **tri-state**:

    ==========================================  ===================
    Condition                                   Result
    ==========================================  ===================
    no monitor / no ``get_pane_option``         ``(None, None)``
    ``get_pane_option`` raised                  ``(None, None)``
    ``get_pane_option`` reported failure        ``(None, None)``
    stamp empty (shadow never analyzed)         ``(False, None)``
    stamp not a float                           ``(None, None)``
    followed pane not observed yet              ``(None, None)``
    ``last_change > analyzed_at + eps``         ``(True, analyzed_at)``
    otherwise                                   ``(False, analyzed_at)``
    ==========================================  ===================

    ``None`` means **"preserve whatever the caller was showing"** — an
    unreadable/malformed stamp or a not-yet-observed followed pane must never
    clear a standing warning. Only an explicit ``False`` clears it. The caller
    owns ``eps`` (one refresh tick, absorbing detection lag) and the banner.

    A *failed* option read is *unverifiable*, never "the shadow has not analyzed
    anything" (t1451). :meth:`TmuxMonitor.get_pane_option` used to collapse
    ``rc != 0`` into ``""``, which landed on the empty-stamp row below and so
    let a tmux timeout **clear** a standing staleness warning — the same
    unverifiable-read-as-a-negative-verdict bug t1446 fixed in
    ``discover_window_panes``. It now returns ``(ok, value)`` and only an
    ``ok`` read reaches the stamp rows; ``-q`` still makes a genuinely *unset*
    option a verified ``(True, "")``, which is what "never analyzed" means.

    The empty-stamp branch returns **before** the last-change lookup: that
    ordering is a cost gate, not an accident — a shadow that never analyzed
    anything must not provoke a followed-pane query every tick.
    """
    if monitor is None or not hasattr(monitor, "get_pane_option"):
        return None, None
    try:
        # Unpacked INSIDE the try on purpose: a stub still returning a bare
        # string raises here and lands on the preserve branch, which is the
        # only safe direction — `None` never clears a standing warning.
        ok, stamp = await monitor.get_pane_option(
            shadow_pane, SHADOW_ANALYZED_AT_OPTION
        )
    except Exception:
        return None, None  # option read failed — preserve prior state
    if not ok:
        return None, None  # tmux could not answer — preserve prior state
    if not stamp:
        # Shadow has not analyzed anything yet: nothing to warn about.
        return False, None
    try:
        analyzed_at = float(stamp)
    except ValueError:
        return None, None  # malformed stamp — preserve prior state
    last_change = None
    if hasattr(monitor, "get_last_change_wall"):
        last_change = monitor.get_last_change_wall(followed_pane)
    if last_change is None:
        return None, None  # followed pane not observed yet — preserve prior state
    return (last_change > analyzed_at + eps), analyzed_at


class BlockAge(NamedTuple):
    """Verdict of the **block age** signal, with both comparison operands.

    The third freshness signal (t1493), alongside *block identity*
    (``concern_parser.concern_block_signature`` — has this block's text
    changed?) and *read recency* (:func:`compute_shadow_staleness` — did the
    shadow *look* after the agent's last change?). Block age asks the question
    neither of those can: **was this block produced after the agent's last
    change?** A shadow that re-reads the pane and then answers in prose restamps
    its read stamp without emitting anything, which clears read recency while
    leaving stale concerns on screen — the live defect this exists to catch.

    ``applicable`` is **not** redundant with ``stale is None``. "There is no
    block" and "there is a block whose age I cannot establish" are different
    states, and only the second is uncertainty: collapsing them makes a shadow
    used purely to explain the screen report "freshness unknown" forever, about
    feedback that does not exist. The flag travels *with* the verdict so a
    caller cannot pass the inapplicable case along as a bare ``None``.

    Both operands of the comparison are carried because the banner reports how
    far the block predates the change (``last_change_wall - reviewed_epoch``).
    A tuple holding only ``reviewed_epoch`` would leave a formatter able to
    compute nothing but ``now - reviewed_epoch``, which is the block's absolute
    age — a different, plausible-looking, wrong number.
    """

    applicable: bool                # is there a block whose age could be asked?
    stale: bool | None              # None = block present, age unknowable
    reviewed_epoch: float | None    # when the block says it was produced
    last_change_wall: float | None  # what that was compared against


def compute_block_age_staleness(
    capture_text: str, last_change_wall: float | None, eps: float
) -> BlockAge:
    """Does the newest concern block predate the followed agent's last change?

    Pure and synchronous — no tmux, no I/O. Takes the **capture text** rather
    than a pre-parsed ``BlockMeta`` so that this function, and only this
    function, decides applicability; a caller handed a bare ``meta`` cannot tell
    "no block" from "block without a header".

    ================================================  ==========================
    Condition                                         Result
    ================================================  ==========================
    no block evidence at all                          ``(False, None, None, None)``
    block present, no ``Round:`` header (pre-t1159_1) ``(True, None, None, lcw)``
    block present, header clipped by the window       ``(True, None, None, lcw)``
    block present, ``Round:``-shaped but malformed    ``(True, None, None, lcw)``
    header parses, ``reviewed_at`` empty/unparseable  ``(True, None, None, lcw)``
    followed pane not observed yet                    ``(True, None, epoch, None)``
    ``last_change_wall > epoch + eps``                ``(True, True, epoch, lcw)``
    otherwise                                         ``(True, False, epoch, lcw)``
    ================================================  ==========================

    ``stale is None`` means **"cannot tell"** — a block is present but its age
    is not establishable. It is fail-safe in the same direction
    :func:`compute_shadow_staleness` is, but the rule is **not** the blanket
    "preserve whatever the caller was showing" that function documents, and a
    caller must not implement it that way:

    - It must never *clear* a standing ``True`` — a false "stale" costs one
      banner, a false "current" forwards advice the agent has already moved
      past.
    - It **must** be recorded over a ``False``. A pane that legitimately read
      "current" and then grows a block whose age is unknowable has become *less*
      certain, not more; preserving the ``False`` there hides the newly
      unverifiable block as current, which is the precise failure this signal
      exists to remove.

    **This applies only to a caller that persists a verdict across ticks.** A
    caller that computes the tri-state and presents it immediately — both
    ``monitor_app`` sites, and the picker modal on either app — has no prior
    state to preserve and simply renders what it got; ``None`` is its own
    presentation there, not a decision. Minimonitor does retain a verdict (its
    live banner), and centralizes every such write in
    ``MiniMonitorApp._record_combined_staleness`` so the rule exists once.

    ``eps`` is the caller's refresh epsilon — the same value the read-recency
    compare uses, absorbing up-to-one-tick change-detection lag.
    """
    if not contains_block_evidence(capture_text):
        return BlockAge(False, None, None, None)
    meta = parse_block_meta(capture_text)
    if meta is None:
        return BlockAge(True, None, None, last_change_wall)
    epoch = parse_reviewed_at_epoch(meta.reviewed_at)
    if epoch is None:
        return BlockAge(True, None, None, last_change_wall)
    if last_change_wall is None:
        return BlockAge(True, None, epoch, None)
    return BlockAge(True, last_change_wall > epoch + eps, epoch, last_change_wall)


def combine_staleness(read: bool | None, block: BlockAge) -> bool | None:
    """Fail-safe join of read recency and block age (t1493).

    Precedence: an inapplicable block age contributes **nothing** (the verdict
    is read recency, unchanged — a pane with no concern block is not dragged
    into uncertainty it has no reason to be in); otherwise ``True`` wins, then
    ``None``, then ``False``.

    So a *present* pre-header block with a clean read stamp resolves to ``None``
    ("cannot tell"), never ``False`` — which is the whole point: before this
    signal existed, exactly that case rendered as "current".

    **This function is total and stateless**; it knows nothing about a prior
    verdict, and most callers need none — they render the value they just
    computed. Only a caller that *retains* a verdict between ticks (minimonitor's
    live banner) has to decide whether a returned ``None`` may overwrite what is
    already on screen; that decision preserves only a standing ``True`` — see
    :func:`compute_block_age_staleness`. Such a caller must not be "improved"
    into preserving any non-``None`` prior: recording ``None`` over ``False`` is
    an escalation and is required.
    """
    if not block.applicable:
        return read
    if read is True or block.stale is True:
        return True
    if read is False and block.stale is False:
        return False
    return None


def count_other_real_agents(
    pane_records: Iterable[tuple[str, bool]], exclude_pane_id: str
) -> int:
    """Count panes that are *real* agents (not helper panes), excluding one.

    ``pane_records`` is an iterable of ``(pane_id, is_helper)`` pairs. Helper
    classification (companion process or shadow marker) is decided by the
    caller, keeping this counting logic pure and import-free for unit tests.
    Used by :meth:`TmuxMonitor.kill_agent_pane_smart` to decide whether the
    window should collapse (no real agents left) or only the pane be killed.
    """
    return sum(
        1
        for pane_id, is_helper in pane_records
        if pane_id != exclude_pane_id and not is_helper
    )


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
    # Non-empty ⇒ this pane is a shadow companion (t986/t1133): the value is the
    # FOLLOWED agent's pane id (from `@aitask_shadow_target`). Shadow panes are
    # excluded from agent-facing discovery and from `_pane_cache`; they exist
    # only in the shadow-status capture path (see `_parse_list_panes`).
    shadow_target: str = ""
    # Lines in the pane's scrollback history (`#{history_size}`), from
    # discovery. A monotonic-growth signal for the review loop's work
    # classifier (t1159_2): real output scrolls lines into history while
    # in-place widget redraws do not (measured live — selection navigation
    # leaves it unchanged, a plan revision grew it 28→61). None when the
    # constructing path did not supply it (older stubs, hand-built infos).
    history_size: int | None = None


@dataclass
class PaneSnapshot:
    pane: TmuxPaneInfo
    content: str            # last N lines of captured text
    timestamp: float        # time.monotonic()
    idle_seconds: float     # seconds since last content change
    is_idle: bool           # idle_seconds > threshold (only meaningful for AGENT panes)
    awaiting_input: bool = False
    awaiting_input_kind: str = ""   # name of the first matching prompt pattern
    # Resolution provenance for `awaiting_input_kind` (t1467). `scoped` False
    # means the kind came from the UNSCOPED flat list because the pane's command
    # did not resolve to a known agent — a common case, not an edge (a Codex
    # pane reports `node`). Consumers must not present the two regimes alike.
    agent_key: str = ""
    scoped: bool = False


# %begin / %end / %error <epoch> <cmd_id> <flags>
# Flags is a bitmask; bit 1 means the block is the response to a command
# issued via this control client. Server-emitted blocks (e.g., the implicit
# attach acknowledgment) have bit 1 unset and must not be delivered to
# pending callers.
_HEAD_RE = re.compile(r"^%(begin|end|error)\s+\d+\s+(\d+)\s+(\d+)\s*$")
_EXIT_RE = re.compile(r"^%exit(?:\s+.*)?$")

_DEFAULT_STREAM_LIMIT = 4 * 1024 * 1024  # 4 MiB; default asyncio is 64 KiB
_DEFAULT_CLOSE_TIMEOUT = 2.0


def _quote_arg(arg: str) -> str:
    """Quote one tmux command argument for the control-mode wire format.

    tmux's command parser tokenizes on whitespace outside quotes; inside
    `"..."` it interprets `\\\\`, `\\"`, and a few other escapes. We escape
    only `\\` → `\\\\` and `"` → `\\"`. Literal tab bytes (`0x09`) inside
    the quoted string are preserved — tmux's lexer accepts them, and this
    matches the byte-for-byte wire format the existing subprocess path
    passes via argv (notably the format string for `list-panes -F`).
    """
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"') + '"'


class TmuxControlClient:
    """Single persistent `tmux -C` control client."""

    def __init__(
        self,
        session: str,
        command_timeout: float = 5.0,
        socket_args: list[str] | None = None,
    ):
        self.session = session
        self.command_timeout = command_timeout
        # Socket flag (``-L <name>`` or ``[]``) cached once — never re-read
        # per request (this client serves the monitor refresh hot path). When
        # not supplied, resolved from ``AITASKS_TMUX_SOCKET`` via the gateway so
        # the control attach converges on the same socket as TmuxClient (t952_3).
        self._socket_args = (
            list(socket_args) if socket_args is not None else tmux_socket_args()
        )
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._pending: "collections.deque[asyncio.Future]" = collections.deque()
        # (cmd_id, buf, deliver) — `deliver` is False for server-emitted
        # blocks (flags bit 1 unset); their bodies are dropped at end/error.
        self._capturing: Optional[tuple[int, list[str], bool]] = None
        self._write_lock = asyncio.Lock()
        self._alive = False

    @property
    def is_alive(self) -> bool:
        return self._alive

    def _attach_argv(self) -> list[str]:
        """Build the ``tmux -C attach`` argv, with the socket flag threaded in.

        The cached socket flag goes between ``"tmux"`` and ``"-C"`` so a
        dedicated-socket move (``AITASKS_TMUX_SOCKET``) reaches the control
        channel exactly as it reaches TmuxClient's subprocess path. Extracted as
        a method so the argv is unit-testable without spawning a process.
        """
        return [
            "tmux", *self._socket_args, "-C", "attach", "-t", self.session,
            "-f", "no-output,ignore-size",
        ]

    async def start(self) -> bool:
        """Spawn `tmux -C attach` and start the reader task.

        Returns False if `tmux` is not on PATH or the attach fails (e.g.,
        the target session does not exist). Does not raise on those paths
        — callers fall back to subprocess.
        """
        if self._proc is not None:
            return self._alive
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *self._attach_argv(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=_DEFAULT_STREAM_LIMIT,
            )
        except (FileNotFoundError, OSError):
            self._proc = None
            return False

        # Attach can fail asynchronously — give the child a brief moment to
        # decide. If it has already exited by the time we look, the attach
        # failed (typically: session does not exist). asyncio's Process
        # exposes `returncode` which is non-None once exited.
        await asyncio.sleep(0.05)
        if self._proc.returncode is not None:
            self._proc = None
            return False

        self._alive = True
        self._reader_task = asyncio.create_task(self._reader_loop())
        return True

    async def _reader_loop(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        try:
            while True:
                line_bytes = await self._proc.stdout.readline()
                if not line_bytes:
                    break  # EOF
                line = line_bytes.decode("utf-8", errors="replace")
                if line.endswith("\n"):
                    line = line[:-1]

                if self._capturing is not None:
                    cmd_id, buf, deliver = self._capturing
                    m = _HEAD_RE.match(line)
                    if m and m.group(1) in ("end", "error") and int(m.group(2)) == cmd_id:
                        rc = 0 if m.group(1) == "end" else 1
                        body = "\n".join(buf) + ("\n" if buf else "")
                        self._capturing = None
                        if deliver:
                            self._resolve_next((rc, body))
                        # Server-emitted block (e.g., attach ack): drop.
                    else:
                        buf.append(line)
                    continue

                m = _HEAD_RE.match(line)
                if m and m.group(1) == "begin":
                    deliver = (int(m.group(3)) & 1) != 0
                    self._capturing = (int(m.group(2)), [], deliver)
                elif _EXIT_RE.match(line):
                    break  # tmux server is going away
                # Any other %-line outside a Capturing block is an async
                # event (filtered to `no-output`-only by the spawn flags,
                # but tmux can still emit %sessions-changed, %client-detached,
                # etc.). Discard.
        except (asyncio.CancelledError, ConnectionResetError, OSError):
            pass
        finally:
            self._teardown_pending()

    def _resolve_next(self, result: tuple[int, str]) -> None:
        if not self._pending:
            return  # spurious response (no caller waiting); drop on the floor
        fut = self._pending.popleft()
        if not fut.done():
            fut.set_result(result)

    def _teardown_pending(self) -> None:
        self._alive = False
        # If a capture was in flight, drop it — the corresponding future is
        # the leftmost in _pending and gets resolved with (-1, "") below.
        self._capturing = None
        while self._pending:
            fut = self._pending.popleft()
            if not fut.done():
                fut.set_result((-1, ""))

    async def request(
        self, args: list[str], timeout: float | None = None
    ) -> tuple[int, str]:
        """Issue one tmux command; return `(rc, stdout_text)`.

        rc semantics mirror `lib.tmux_exec.TmuxClient.run_async`:
        - `0` on success
        - `1` on tmux command error (`%error` reply)
        - `-1` on transport failure (client dead, broken pipe, timeout)

        On `-1`, the client is marked dead; the next `request()` will also
        return `(-1, "")` until `start()` is called again.
        """
        if not self._alive or self._proc is None or self._proc.stdin is None:
            return (-1, "")

        cmd_line = " ".join(_quote_arg(a) for a in args) + "\n"
        fut: asyncio.Future = asyncio.get_running_loop().create_future()

        async with self._write_lock:
            if not self._alive or self._proc.stdin is None:
                return (-1, "")
            self._pending.append(fut)
            try:
                self._proc.stdin.write(cmd_line.encode("utf-8"))
                await self._proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError, OSError):
                self._teardown_pending()
                return (-1, "")

        try:
            effective_timeout = timeout if timeout is not None else self.command_timeout
            return await asyncio.wait_for(fut, timeout=effective_timeout)
        except asyncio.TimeoutError:
            # We can't reliably correlate any future responses to in-flight
            # callers anymore — mark dead and let everyone fall back.
            self._teardown_pending()
            return (-1, "")

    async def close(self) -> None:
        """Shut down the control client cleanly.

        Closes stdin (tmux drops the control client on EOF), waits briefly
        for `proc.wait()`, kills if it's still running, then cancels the
        reader task. Resolves any remaining futures with `(-1, "")`.
        Idempotent.
        """
        self._alive = False
        proc = self._proc
        if proc is None:
            self._teardown_pending()
            return

        if proc.stdin is not None and not proc.stdin.is_closing():
            with contextlib.suppress(Exception):
                proc.stdin.close()

        try:
            await asyncio.wait_for(proc.wait(), timeout=_DEFAULT_CLOSE_TIMEOUT)
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            with contextlib.suppress(Exception):
                await proc.wait()

        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._reader_task

        self._teardown_pending()
        self._proc = None
        self._reader_task = None


_BACKEND_READY_TIMEOUT = 2.0
_BACKEND_START_TIMEOUT = 5.0
_BACKEND_STOP_TIMEOUT = 3.0
_BACKEND_THREAD_JOIN_TIMEOUT = 3.0

# Supervisor / reconnect tuning. Backoffs are seconds between successive
# reconnect attempts; the supervisor sleeps the backoff *before* each
# attempt, so the first respawn is delayed by 0.5 s after the prior client
# is observed dead. After `_RECONNECT_MAX_ATTEMPTS` consecutive failed
# spawns the supervisor exits and the backend stays in `FALLBACK` for the
# rest of its life. `_DEATH_POLL_INTERVAL` is the cadence at which the
# supervisor polls `client.is_alive` while the channel is healthy — kept
# tighter than the typical monitor refresh so the badge flips quickly when
# the channel breaks.
_RECONNECT_BACKOFFS = (0.5, 1.0, 2.0, 4.0, 8.0)
_RECONNECT_MAX_ATTEMPTS = 5
_DEATH_POLL_INTERVAL = 0.5


class TmuxControlState(enum.Enum):
    """Lifecycle state of a `TmuxControlBackend`'s control channel."""
    CONNECTED = "connected"        # client attached and serving requests
    RECONNECTING = "reconnecting"  # supervisor is respawning the client
    FALLBACK = "fallback"          # max attempts exhausted; subprocess only
    STOPPED = "stopped"            # backend.stop() called or never started


class TmuxControlBackend:
    """Owns a dedicated asyncio loop in a background thread that drives a
    `TmuxControlClient`.

    Provides sync (`request_sync`) and async (`request_async`) entry points;
    both route through `asyncio.run_coroutine_threadsafe` so callers on any
    thread/loop see consistent semantics. The backend exists so that sync
    user-action call sites (Textual handlers, etc.) can reach the control
    client without deadlocking the reader task — the reader runs on the
    backend's bg loop, not on the calling thread's loop.

    Subprocess fallback is the caller's responsibility: this class only
    surfaces `(-1, "")` on transport failure.
    """

    def __init__(
        self,
        session: str,
        command_timeout: float = 5.0,
        socket_args: list[str] | None = None,
    ):
        self.session = session
        self.command_timeout = command_timeout
        # Cached socket flag, passed to every client this backend constructs
        # (initial start + every supervisor reconnect) so a reconnected channel
        # keeps the same socket. Resolved from AITASKS_TMUX_SOCKET when not
        # supplied (unset env → dedicated `-L ait` socket, t953).
        self._socket_args = (
            list(socket_args) if socket_args is not None else tmux_socket_args()
        )
        self._client: Optional[TmuxControlClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._state: TmuxControlState = TmuxControlState.STOPPED
        self._state_lock = threading.Lock()
        self._reconnect_task: Optional[asyncio.Task] = None
        self._stop_requested: bool = False

    @property
    def is_alive(self) -> bool:
        return self._client is not None and self._client.is_alive

    @property
    def state(self) -> TmuxControlState:
        """Current channel state. Thread-safe; safe to call from the UI loop."""
        with self._state_lock:
            return self._state

    def _set_state(self, s: TmuxControlState) -> None:
        with self._state_lock:
            self._state = s

    def start(self) -> bool:
        """Start bg thread + loop, then start the client on it.

        Returns True iff the client successfully attached. Idempotent: a
        second call while already started returns the current `is_alive`
        without spawning a second thread.
        """
        if self._thread is not None:
            return self.is_alive
        self._stop_requested = False
        self._ready.clear()
        thread = threading.Thread(
            target=self._thread_main, name="tmux-control-loop", daemon=True
        )
        thread.start()
        if not self._ready.wait(timeout=_BACKEND_READY_TIMEOUT) or self._loop is None:
            # Loop never came up — abandon the thread (daemon=True will clean
            # it up at process exit). Reset state so a future start() retries.
            self._thread = None
            self._loop = None
            return False
        self._thread = thread
        client = TmuxControlClient(
            self.session, self.command_timeout, socket_args=self._socket_args
        )
        cf = asyncio.run_coroutine_threadsafe(client.start(), self._loop)
        try:
            ok = cf.result(timeout=_BACKEND_START_TIMEOUT)
        except Exception:
            ok = False
        if ok:
            self._client = client
            self._set_state(TmuxControlState.CONNECTED)
            self._spawn_supervisor()
            return True
        # Client did not attach. Tear down the thread so we don't leak it.
        self.stop()
        return False

    def _spawn_supervisor(self) -> None:
        """Schedule the reconnect supervisor on the bg loop (fire-and-forget).

        Stores the resulting `asyncio.Task` in `self._reconnect_task` from
        the bg loop's thread, so cancellation in `stop()` always reads a
        consistent value.
        """
        loop = self._loop
        if loop is None:
            return

        def _create_task() -> None:
            self._reconnect_task = loop.create_task(self._supervisor_loop())

        loop.call_soon_threadsafe(_create_task)

    async def _supervisor_loop(self) -> None:
        """Watch the active client; respawn on death with bounded backoff.

        Runs on the bg loop. Polls `client.is_alive` at
        `_DEATH_POLL_INTERVAL`; on death, attempts up to
        `_RECONNECT_MAX_ATTEMPTS` reconnects spaced by `_RECONNECT_BACKOFFS`.
        On success, swaps `self._client` to the fresh client and returns to
        polling. On exhaustion, sets `FALLBACK` and exits — the backend
        stays subprocess-only for the rest of its life.

        Cooperative shutdown: `stop()` sets `_stop_requested = True` and
        cancels the task. Both paths exit cleanly.
        """
        try:
            while not self._stop_requested:
                # Phase 1: wait for the current client to die.
                while (
                    self._client is not None
                    and self._client.is_alive
                    and not self._stop_requested
                ):
                    await asyncio.sleep(_DEATH_POLL_INTERVAL)
                if self._stop_requested:
                    return

                # Phase 2: client is dead. Try to reconnect with backoff.
                self._set_state(TmuxControlState.RECONNECTING)
                attempts = 0
                reconnected = False
                while (
                    attempts < _RECONNECT_MAX_ATTEMPTS
                    and not self._stop_requested
                ):
                    delay = _RECONNECT_BACKOFFS[
                        min(attempts, len(_RECONNECT_BACKOFFS) - 1)
                    ]
                    await asyncio.sleep(delay)
                    if self._stop_requested:
                        return
                    new_client = TmuxControlClient(
                        self.session, self.command_timeout,
                        socket_args=self._socket_args,
                    )
                    if await new_client.start():
                        self._client = new_client
                        self._set_state(TmuxControlState.CONNECTED)
                        reconnected = True
                        break
                    attempts += 1

                if not reconnected:
                    self._set_state(TmuxControlState.FALLBACK)
                    return
        except asyncio.CancelledError:
            # Cooperative shutdown — fall through. State is updated by stop().
            return

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    def stop(self) -> None:
        """Close the client (on bg loop), stop the loop, join the thread.

        Idempotent. Safe to call when start() failed partway through. Also
        cancels the reconnect supervisor (if any) before tearing down the
        client, so an in-flight reconnect attempt cannot create a new
        `tmux -C attach` subprocess after `stop()` returns.
        """
        self._stop_requested = True
        loop = self._loop
        client = self._client
        thread = self._thread
        # Cancel the supervisor before closing the client so it can't
        # respawn a fresh one in the gap between client.close() and the
        # loop stopping.
        if loop is not None and self._reconnect_task is not None:
            with contextlib.suppress(Exception):
                cf = asyncio.run_coroutine_threadsafe(
                    self._cancel_reconnect_task(), loop
                )
                cf.result(timeout=1.0)
        if loop is not None and client is not None:
            with contextlib.suppress(Exception):
                cf = asyncio.run_coroutine_threadsafe(client.close(), loop)
                cf.result(timeout=_BACKEND_STOP_TIMEOUT)
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None and thread.is_alive():
            thread.join(timeout=_BACKEND_THREAD_JOIN_TIMEOUT)
        self._client = None
        self._loop = None
        self._thread = None
        self._reconnect_task = None
        self._ready.clear()
        self._set_state(TmuxControlState.STOPPED)

    async def _cancel_reconnect_task(self) -> None:
        """Cancel the supervisor task and wait for it to finish.

        Runs on the bg loop. Reads `self._reconnect_task` from the same
        loop that created it, so the read is consistent. Idempotent —
        safe if the task already finished or was never created.
        """
        task = self._reconnect_task
        if task is None or task.done():
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    def request_sync(
        self, args: list[str], timeout: Optional[float] = None
    ) -> tuple[int, str]:
        """Issue a tmux command and block until the response arrives.

        Returns `(rc, stdout)`. `(-1, "")` on transport failure (client
        dead, loop unavailable, or future timeout). Safe to call from any
        thread, including from inside an asyncio handler running on a
        different loop than the backend.
        """
        loop = self._loop
        client = self._client
        if loop is None or client is None or not client.is_alive:
            return (-1, "")
        eff = timeout if timeout is not None else self.command_timeout
        try:
            cf = asyncio.run_coroutine_threadsafe(
                client.request(args, timeout=eff), loop
            )
        except RuntimeError:
            # Loop closed between the alive check and scheduling.
            return (-1, "")
        try:
            return cf.result(timeout=eff + 1.0)
        except Exception:
            with contextlib.suppress(Exception):
                cf.cancel()
            return (-1, "")

    async def request_async(
        self, args: list[str], timeout: Optional[float] = None
    ) -> tuple[int, str]:
        """Issue a tmux command from an async caller on a different loop.

        The caller awaits the result on its own loop; the request executes
        on the backend's bg loop.
        """
        loop = self._loop
        client = self._client
        if loop is None or client is None or not client.is_alive:
            return (-1, "")
        eff = timeout if timeout is not None else self.command_timeout
        try:
            cf = asyncio.run_coroutine_threadsafe(
                client.request(args, timeout=eff), loop
            )
        except RuntimeError:
            return (-1, "")
        try:
            return await asyncio.wrap_future(cf)
        except Exception:
            return (-1, "")


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
        prompt_patterns: list[PromptPattern] | None = None,
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
        self.prompt_patterns = list(prompt_patterns) if prompt_patterns is not None else all_patterns()

        self._last_content: dict[str, str] = {}
        self._last_change_time: dict[str, float] = {}
        # Monotonic capture generation (t1111_4). Reserved at the START of every
        # async capture path and bumped by the sync `_finalize_capture` write.
        # A guarded commit writes `_last_content` only if its reserved gen still
        # equals this — so the capture with the latest reservation wins and no
        # superseded (out-of-order) cycle corrupts the idle clock. Lives here,
        # beside the state it guards, so every caller (monitor, minimonitor,
        # pusher, applink router) is protected uniformly.
        self._capture_generation: int = 0
        # Discovery-derived liveness facts (t1326), keyed by capture generation
        # until that generation's commit wins. See _record_discovery_facts.
        self._discovery_facts: dict[int, tuple[frozenset, frozenset]] = {}
        self._enumerated_sessions: frozenset[str] = frozenset()
        self._discovered_agents: frozenset = frozenset()
        self._pane_cache: dict[str, TmuxPaneInfo] = {}
        # Companion-verdict memo (t1382): pane_id → (pane_pid, session, cached_at)
        # for panes CONFIRMED to be a monitor/minimonitor companion. Only
        # *positive* verdicts are stored, and that asymmetry is the whole point:
        # the launch chain execs in place (`ait` → `aitask_monitor.sh` →
        # `exec python monitor/monitor_app.py`), so a companion's cmdline flips
        # from a non-matching one to a matching one under an UNCHANGED pid. A
        # cached negative would therefore keep listing a companion pane as an
        # agent-facing pane — the exact symptom `_parse_list_panes` filters out.
        # Negatives are re-probed every discovery pass, so that transition is
        # picked up on the next refresh. See `_is_companion_pane`.
        self._companion_memo: dict[str, tuple[int, str, float]] = {}
        # Clock seam for the memo's TTL. An instance attribute (not a bound
        # method) so tests can drive the TTL deterministically instead of
        # sleeping — see aidocs/framework/testing_conventions.md.
        self._monotonic = time.monotonic
        # Shadow-status map (t1133): followed pane id → the bound shadow pane's
        # latest PaneSnapshot. Rebuilt wholesale by every `commit_snapshots`
        # (loop-side, generation-guarded — invariant B) and cleared by the sync
        # `capture_all` path, so it can never go stale: absent, never frozen.
        # Shadow panes themselves are NEVER in `_pane_cache` (cache-boundary
        # invariant — applink `get_pane`/`capture_pane` stay shadow-blind).
        self._shadow_snapshots: dict[str, PaneSnapshot] = {}
        # Shadow WRITE ordering (t1216_1) — separate from `_capture_generation`
        # so a single-shadow refresh can never supersede a full refresh. Both
        # writers reserve from this one counter in the statement immediately
        # before they issue their own shadow capture-pane, so the seq is a
        # faithful proxy for READ order and every shadow write is totally
        # ordered. `_shadow_snapshot_seq` records the seq each live entry was
        # read at; `_full_shadow_seq` carries the running full refresh's
        # reservation from its capture site to `commit_snapshots`.
        self._shadow_write_seq: int = 0
        self._shadow_snapshot_seq: dict[str, int] = {}
        self._full_shadow_seq: tuple[int, int] | None = None
        self._sessions_cache: tuple[float, list[AitasksSession]] | None = None
        self._compare_mode_overrides: dict[str, str] = {}
        self._backend: TmuxControlBackend | None = None
        # Gateway owns the exec strategy (control-client-vs-subprocess dispatch)
        # and the socket flag; tmux_run / _tmux_async delegate to it (t952_3).
        self._tmux = TmuxClient()

    async def start_control_client(self) -> bool:
        """Start the persistent `tmux -C` backend on a dedicated bg thread.

        Kept `async` so existing call sites (`await monitor.start_control_client()`)
        do not need to change. The body is synchronous — the bg thread does
        the actual asyncio work — so awaiting it just yields once.
        """
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

    def control_state(self) -> TmuxControlState:
        """Backend channel state, or `STOPPED` if no backend is attached."""
        if self._backend is None:
            return TmuxControlState.STOPPED
        return self._backend.state

    async def _tmux_async(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        # Thin delegation: the gateway owns the control-client-vs-subprocess
        # dispatch (t952_3). Signature unchanged so all monitor call sites stay.
        return await self._tmux.run_async_via_control(
            self._backend, args, timeout=timeout
        )

    # -- Capture generation + offload seam (t1111_4) ---------------------------

    def _next_generation(self) -> int:
        """Reserve and return the next capture generation (see `__init__`)."""
        self._capture_generation += 1
        return self._capture_generation

    # -- discovery-derived liveness facts (t1326) ------------------------------
    #
    # Published for the prioritized-agent mark purge, which must distinguish
    # "this session was enumerated and the agent is gone" from "we could not see
    # this session". Both answers come from DISCOVERY, never from the committed
    # snapshots: a pane whose content capture failed is dropped by
    # `commit_snapshots`, and treating that as a departed agent would delete a
    # live mark.

    def _record_discovery_facts(
        self, gen: int, panes, shadows, enumerated=None
    ) -> None:
        """Stash this generation's discovery facts until its commit wins.

        ``enumerated`` is the set of sessions whose ``list-panes`` returned
        ``rc == 0``, reported by discovery independently of what survives
        parsing and filtering. That independence is the point: a session whose
        last agent has exited may retain only the excluded companion pane, so it
        parses to ZERO panes while being perfectly observable. Inferring the set
        from the surviving panes would call it unenumerated, leave it
        un-sweepable, and strand the departed agent's mark until TTL expiry.

        ``None`` means the caller could not supply it (a stubbed discovery in
        tests); the pane-derived set is then the best available approximation.
        """
        if enumerated is None:
            enumerated = frozenset(
                p.session_name
                for p in list(panes) + list(shadows)
                if p.session_name
            )
        sessions = frozenset(enumerated)
        agents = frozenset(
            (p.session_name, p.window_name)
            for p in panes
            if p.category == PaneCategory.AGENT and p.session_name
        )
        self._discovery_facts[gen] = (sessions, agents)
        # Prune anything older than the live reservation; those batches can no
        # longer commit, so their facts are unreachable.
        for stale in [g for g in self._discovery_facts if g < gen]:
            del self._discovery_facts[stale]

    def _publish_discovery_facts(self, gen: int) -> None:
        """Promote a winning generation's facts. Called only past the guard."""
        facts = self._discovery_facts.pop(gen, None)
        if facts is not None:
            self._enumerated_sessions, self._discovered_agents = facts

    def last_enumerated_sessions(self) -> frozenset[str]:
        """Sessions whose panes were listed in the last *committed* discovery.

        A session absent here was not observed at all — not running, its
        `list-panes` failed, or it lives on another tmux socket — and is
        therefore never a valid basis for concluding an agent departed.
        """
        return self._enumerated_sessions

    def last_discovered_agents(self) -> frozenset:
        """``(session_name, window_name)`` for every agent window discovered in
        the last committed cycle, including ones whose content capture failed."""
        return self._discovered_agents

    @property
    def capture_generation(self) -> int:
        """Current capture generation; callers compare their reserved gen to this
        to detect supersession without touching a private attr."""
        return self._capture_generation

    def _next_shadow_write_seq(self) -> int:
        """Reserve the next shadow WRITE sequence number (t1216_1).

        Deliberately NOT `_next_generation`: bumping the capture generation from
        a single-shadow refresh would supersede an in-flight full refresh. Every
        writer of `_shadow_snapshots` reserves from here in the statement
        immediately before issuing its own shadow capture — see the class
        docstring of :meth:`refresh_shadow_snapshot`.
        """
        self._shadow_write_seq += 1
        return self._shadow_write_seq

    def _clear_shadow_snapshots(self) -> None:
        """Drop all shadow state as one unit (t1216_1).

        `_shadow_snapshots` and `_shadow_snapshot_seq` are two halves of one
        value — every read of the seq map assumes the matching snapshot exists.
        Clearing them together in a single method keeps that invariant local
        instead of leaving it to each call site to remember.
        """
        self._shadow_snapshots = {}
        self._shadow_snapshot_seq = {}

    async def _run_offloaded(self, fn):
        """Run pure CPU work `fn` off the event loop (t1111_4).

        The single injectable offload seam: production hops to a worker thread via
        `asyncio.to_thread`; tests override this to run `fn` synchronously and to
        control resolution order deterministically (invariant F — no sleep-based
        timing). `fn` MUST be pure compute over plain data (invariant A).
        """
        return await asyncio.to_thread(fn)

    def tmux_run(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        """Sync user-action wrapper — control-client when alive, subprocess fallback.

        Returns `(rc, stdout)`. `rc` semantics:
          * `0` on success
          * `1` on tmux command error
          * `-1` on transport failure or subprocess error.

        Safe to call from sync Textual handlers because the control client
        runs on a background loop; this method blocks the caller's thread,
        not the bg loop's reader task. The dispatch itself lives in the gateway
        (`TmuxClient.run_via_control`, t952_3); this is a thin delegation.
        """
        return self._tmux.run_via_control(self._backend, args, timeout=timeout)

    async def tmux_run_async(
        self, args: list[str], timeout: float = 5.0
    ) -> tuple[int, str]:
        """Async sibling of :meth:`tmux_run` — same ``(rc, stdout)`` contract.

        Use from async Textual handlers / the refresh loop so a tmux stall never
        blocks the event loop (the sync :meth:`tmux_run` would block the calling
        thread, which on an async path is the loop thread). Thin public alias for
        the internal :meth:`_tmux_async`.
        """
        return await self._tmux_async(args, timeout=timeout)

    async def get_pane_option(
        self, pane_id: str, option: str, timeout: float = 2.0
    ) -> tuple[bool, str]:
        """Read a pane-scoped tmux user-option, discriminating failure from unset.

        Gateway-routed (``show-options -pqv``) so all tmux access stays inside
        the monitor per ``tmux_gateway.md``. ``-q`` keeps an unset option quiet
        and ``-v`` prints just the value. Used by minimonitor's shadow-freshness
        check (t1104).

        Returns ``(ok, value)``. ``ok`` is ``False`` only when tmux could not
        answer (transport failure / timeout ``rc == -1``, or a tmux command
        error ``rc == 1``); ``(True, "")`` is a *verified* "this option is not
        set". The pair mirrors :func:`find_shadow_pane_status` and exists for
        the reason t1446's ``(observed, panes)`` does: this used to return ``""``
        on failure, and :func:`compute_shadow_staleness` read that as "the shadow
        has never analyzed anything: nothing to warn about", so a tmux failure
        *cleared* a standing staleness banner (t1451). A 2-tuple cannot be
        consumed without binding the flag, whereas ``""`` is silently falsy.
        """
        rc, out = await self.tmux_run_async(
            ["show-options", "-pqv", "-t", pane_id, option], timeout=timeout
        )
        if rc != 0:
            return (False, "")
        return (True, out.strip())

    def get_last_change_wall(self, pane_id: str) -> float | None:
        """Wall-clock epoch (approx) when ``pane_id``'s content last changed.

        Converts the monotonic ``_last_change_time`` (set in ``_finalize_capture``
        when the captured content differs) into wall-clock so it can be compared
        against another process's epoch stamp (the shadow's ``@aitask_shadow_
        analyzed_at``). Returns ``None`` if the pane has not been observed yet.
        The recorded instant is the *detection* tick, so it lags the real change
        by up to one refresh interval — callers absorb that with an epsilon
        (t1104).
        """
        mono = self._last_change_time.get(pane_id)
        if mono is None:
            return None
        return time.time() - (time.monotonic() - mono)

    def resize_pane(
        self, pane: str, *, x: int | None = None, y: int | None = None,
        timeout: float = 2.0,
    ) -> tuple[int, str]:
        """Resize a pane via the gateway's subprocess path.

        ``resize-pane`` is still owned by ``TmuxClient.resize_pane`` so socket
        selection and argv construction stay centralized. This intentionally
        does not pass the control backend: minimonitor re-pinning happens from
        Textual's resize handler, and tmux can lose immediate control-mode
        resize commands during a window-growth reflow.
        """
        return self._tmux.resize_pane(pane, x=x, y=y, timeout=timeout)

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

    async def _discover_sessions_cached_async(self) -> list[AitasksSession]:
        """Async sibling of `_discover_sessions_cached` for refresh-loop use."""
        now = time.monotonic()
        if self._sessions_cache is not None:
            cached_at, sessions = self._sessions_cache
            if now - cached_at < self._SESSIONS_CACHE_TTL:
                return sessions
        sessions = await discover_aitasks_sessions_async()
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

    async def get_session_to_project_mapping_async(self) -> dict[str, Path]:
        """Async sibling of `get_session_to_project_mapping` for refresh-loop use."""
        sessions = await self._discover_sessions_cached_async()
        return {s.session: s.project_root for s in sessions}

    def classify_pane(self, window_name: str) -> PaneCategory:
        for prefix in self.agent_prefixes:
            if window_name.startswith(prefix):
                return PaneCategory.AGENT
        if window_name in self.tui_names:
            return PaneCategory.TUI
        if window_name.startswith(BRAINSTORM_PREFIX):
            return PaneCategory.TUI
        return PaneCategory.OTHER

    def _is_companion_pane(self, pane_id: str, pane_pid: int, session: str) -> bool:
        """Memoized companion check for the discovery hot path.

        Wraps :func:`_is_companion_process` (which reads ``/proc`` on Linux and
        shells out to ``ps`` everywhere else) so the per-refresh cost of the
        now-unconditional filter in :meth:`_parse_list_panes` is bounded.

        **Only positive verdicts are cached, deliberately.** A launcher pane
        ``exec``s into ``monitor_app`` under an unchanged pid, so ``False`` can
        become ``True`` for the same ``(pane_id, pane_pid)`` pair; caching that
        negative would leave a companion pane listed until the pane died. The
        reverse transition has no trigger — a running Textual companion does not
        exec away, and once its process exits the pane either disappears (evicted
        by the sweep in ``_parse_list_panes``) or lingers under
        ``remain-on-exit``, where staying hidden is what we want anyway. The TTL
        is a self-healing backstop, not a correctness mechanism.

        ``session`` is stored so the eviction sweep can stay session-scoped:
        ``_parse_list_panes`` runs once per session per tick, and an unscoped
        sweep would evict the other sessions' live entries in multi-session mode.
        """
        now = self._monotonic()
        hit = self._companion_memo.get(pane_id)
        if (
            hit is not None
            and hit[0] == pane_pid
            and now - hit[2] < _COMPANION_MEMO_TTL
        ):
            return True
        if _is_companion_process(pane_pid):
            self._companion_memo[pane_id] = (pane_pid, session, now)
            return True
        self._companion_memo.pop(pane_id, None)
        return False

    def _evict_companion_memo(self, session_name: str, seen: set[str]) -> None:
        """Drop this session's memo entries for panes absent from ``seen``.

        Session-scoped on purpose (see :meth:`_is_companion_pane`). Keeps the
        memo bounded by the live pane set rather than growing for the lifetime
        of the monitor.
        """
        for pane_id, (_pid, sess, _at) in list(self._companion_memo.items()):
            if sess == session_name and pane_id not in seen:
                del self._companion_memo[pane_id]

    _LIST_PANES_FORMAT = "\t".join([
        "#{window_index}", "#{window_name}", "#{pane_index}",
        "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
        "#{pane_width}", "#{pane_height}",
        "#{@aitask_shadow_target}",   # shadow helper marker (t986); "" when unset
        "#{history_size}",   # scrollback-growth work signal (t1159_2)
    ])

    def _parse_list_panes(
        self, stdout: str, session_name: str
    ) -> tuple[list[TmuxPaneInfo], list[TmuxPaneInfo]]:
        """Parse ``list-panes`` output into ``(agent_facing_panes, shadow_panes)``.

        Shadow companion panes (t986) are helpers — kept OUT of the first list
        so they never appear in agent lists, snapshots, or kill/sibling logic,
        exactly like the minimonitor/monitor panes filtered below. The marker is
        authoritative even for a same-window shadow, which shares the agent's
        window name. Since t1133 they are returned separately (second list) so
        the live capture pipeline can classify their state for the shadow-status
        glyph. **Cache-boundary invariant:** only agent-facing panes enter
        ``_pane_cache`` — shadows never do, so every cache-backed consumer
        (``get_pane``, ``capture_pane``, compare-mode state, applink) stays
        shadow-blind by construction.
        """
        panes: list[TmuxPaneInfo] = []
        shadows: list[TmuxPaneInfo] = []
        seen: set[str] = set()   # pane ids observed this pass, for the memo sweep
        # Preserve an empty final @aitask_shadow_target field on non-shadow panes.
        for line in stdout.splitlines():
            parts = line.split("\t")
            # 10 = current format; 9 = pre-history_size lines (test stubs) —
            # still parsed, with history_size None (t1159_2).
            if len(parts) not in (9, 10):
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
            history_size: int | None = None
            if len(parts) > 9:
                try:
                    history_size = int(parts[9])
                except ValueError:
                    history_size = None
            window_name = parts[1]
            seen.add(pane_id)
            if is_shadow_target(parts[8]):
                # Category forced to AGENT: a shadow IS a coding-agent CLI, so
                # the prompt scan + idle bookkeeping must apply regardless of
                # its window name (a same-window shadow shares the agent's).
                shadows.append(TmuxPaneInfo(
                    window_index=parts[0],
                    window_name=window_name,
                    pane_index=parts[2],
                    pane_id=pane_id,
                    pane_pid=pane_pid,
                    current_command=parts[5],
                    width=width,
                    height=height,
                    category=PaneCategory.AGENT,
                    session_name=session_name,
                    shadow_target=parts[8].strip(),
                    history_size=history_size,
                ))
                continue
            category = self.classify_pane(window_name)
            # Filter companion panes (minimonitor/monitor). UNCONDITIONAL by
            # process identity (t1382), like the shadow-helper filter above and
            # unlike the former `category == AGENT and …` form: renaming a window
            # off the `agent-` prefix flips its panes to OTHER, and gating on the
            # category meant the companion stopped being consulted and surfaced
            # as a second card for the renamed window. A companion is a helper
            # regardless of what its window is called.
            if self._is_companion_pane(pane_id, pane_pid, session_name):
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
                history_size=history_size,
            )
            panes.append(pane)
            self._pane_cache[pane_id] = pane
        self._evict_companion_memo(session_name, seen)
        return panes, shadows

    def _target_sessions(self) -> list[str]:
        """Session names to enumerate in multi mode (sorted for stable display)."""
        return sorted(s.session for s in self._discover_sessions_cached())

    async def _target_sessions_async(self) -> list[str]:
        """Async session names to enumerate in multi mode."""
        sessions = await self._discover_sessions_cached_async()
        return sorted(s.session for s in sessions)

    _PANE_SORT_KEY = staticmethod(
        lambda p: (p.session_name, p.window_index, p.pane_index)
    )

    def _discover_panes_multi(
        self,
    ) -> tuple[list[TmuxPaneInfo], list[TmuxPaneInfo], frozenset[str]]:
        """``(panes, shadows, successfully_enumerated_sessions)``."""
        panes: list[TmuxPaneInfo] = []
        shadows: list[TmuxPaneInfo] = []
        ok_sessions: set[str] = set()   # see the async sibling (t1326)
        for sess in self._target_sessions():
            rc, stdout = self.tmux_run([
                "list-panes", "-s", "-t", tmux_session_target(sess),
                "-F", self._LIST_PANES_FORMAT,
            ])
            if rc != 0:
                continue
            ok_sessions.add(sess)
            sess_panes, sess_shadows = self._parse_list_panes(stdout, sess)
            panes.extend(sess_panes)
            shadows.extend(sess_shadows)
        panes.sort(key=self._PANE_SORT_KEY)
        shadows.sort(key=self._PANE_SORT_KEY)
        return panes, shadows, frozenset(ok_sessions)

    async def _discover_panes_multi_async(
        self,
    ) -> tuple[list[TmuxPaneInfo], list[TmuxPaneInfo], frozenset[str]]:
        """``(panes, shadows, successfully_enumerated_sessions)``."""
        sessions = await self._target_sessions_async()
        if not sessions:
            return [], [], frozenset()
        results = await asyncio.gather(*[
            self._tmux_async([
                "list-panes", "-s", "-t", tmux_session_target(sess),
                "-F", self._LIST_PANES_FORMAT,
            ])
            for sess in sessions
        ])
        panes: list[TmuxPaneInfo] = []
        shadows: list[TmuxPaneInfo] = []
        # Sessions whose `list-panes` SUCCEEDED, recorded independently of what
        # survives parsing/filtering (t1326). A session can enumerate cleanly and
        # still yield zero panes — e.g. its last agent exited and only the
        # excluded companion pane remains — and that is a very different fact
        # from "we could not see this session".
        ok_sessions: set[str] = set()
        for sess, (rc, stdout) in zip(sessions, results):
            if rc != 0:
                continue
            ok_sessions.add(sess)
            sess_panes, sess_shadows = self._parse_list_panes(stdout, sess)
            panes.extend(sess_panes)
            shadows.extend(sess_shadows)
        panes.sort(key=self._PANE_SORT_KEY)
        shadows.sort(key=self._PANE_SORT_KEY)
        return panes, shadows, frozenset(ok_sessions)

    def discover_panes(self) -> list[TmuxPaneInfo]:
        """Agent-facing panes only (shadow companions excluded) — the public
        discovery contract every non-shadow consumer relies on."""
        if self.multi_session:
            return self._discover_panes_multi()[0]
        rc, stdout = self.tmux_run([
            "list-panes", "-s", "-t", tmux_session_target(self.session),
            "-F", self._LIST_PANES_FORMAT,
        ])
        if rc != 0:
            return []
        return self._parse_list_panes(stdout, self.session)[0]

    async def discover_panes_async(self) -> list[TmuxPaneInfo]:
        """Async sibling of :meth:`discover_panes` (agent-facing panes only)."""
        return (await self.discover_panes_with_shadows_async())[0]

    async def discover_panes_with_shadows_async(
        self, *, enum_sink: list | None = None,
    ) -> tuple[list[TmuxPaneInfo], list[TmuxPaneInfo]]:
        """Discovery for the live capture pipeline (t1133): returns
        ``(agent_facing_panes, shadow_panes)`` from the SAME ``list-panes``
        output — shadow discovery costs zero extra tmux round-trips."""
        if self.multi_session:
            panes, shadows, ok_sessions = await self._discover_panes_multi_async()
        else:
            rc, stdout = await self._tmux_async(
                ["list-panes", "-s", "-t", tmux_session_target(self.session),
                 "-F", self._LIST_PANES_FORMAT],
            )
            if rc != 0:
                panes, shadows, ok_sessions = [], [], frozenset()
            else:
                panes, shadows = self._parse_list_panes(stdout, self.session)
                ok_sessions = frozenset({self.session})
        # The successfully-enumerated session set is reported through a
        # caller-owned sink rather than the return value (t1326): the 2-tuple
        # return is a widely-stubbed seam, and binding the value to THIS call
        # — instead of an instance attribute — is what stops an overlapping
        # discovery from handing its answer to the wrong capture generation.
        if enum_sink is not None:
            enum_sink.append(ok_sessions)
        return panes, shadows

    def discover_window_panes(
        self, window_id: str
    ) -> tuple[bool, list[TmuxPaneInfo]]:
        """Discover panes in a specific window (not session-wide).

        Uses 'tmux list-panes -t window_id' (no -s flag).
        Does not filter by exclude_pane or update _pane_cache.

        Returns ``(observed, panes)``. ``observed`` is ``True`` only when tmux
        answered (``rc == 0``) **and** every non-blank record parsed. It is
        ``False`` on a transport failure / timeout (``rc == -1``), on a tmux
        command error (``rc == 1``), and on a listing with any unparseable
        record — in which case the panes that *did* parse are still returned,
        so a caller wanting a best-effort list can use them.

        ``observed=False`` means **unverifiable**, never **empty** (t1446).
        Collapsing the two is what let a 5-second tmux stall read as "no panes
        left in my window" and quit every minimonitor companion at once; the
        pair exists so no caller can make that mistake by omission. A dropped
        record matters for the same reason: a truncated sibling row leaves a
        listing that looks exactly like solitude.
        """
        fmt = "\t".join([
            "#{window_index}", "#{window_name}", "#{pane_index}",
            "#{pane_id}", "#{pane_pid}", "#{pane_current_command}",
            "#{pane_width}", "#{pane_height}",
        ])
        rc, stdout = self.tmux_run(["list-panes", "-t", window_id, "-F", fmt])
        if rc != 0:
            return (False, [])

        # Cleared by any dropped record — see the docstring. Blank lines are
        # not records and never clear it.
        complete = True
        panes: list[TmuxPaneInfo] = []
        for line in stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 8:
                complete = False
                continue
            try:
                pane_pid = int(parts[4])
                width = int(parts[6])
                height = int(parts[7])
            except ValueError:
                complete = False
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
        return (complete, panes)

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

    def _apply_bookkeeping(
        self,
        pane: TmuxPaneInfo,
        content: str,
        result: ClassifyResult,
        now: float,
    ) -> PaneSnapshot:
        """Loop/sync-side commit of a pre-computed :class:`ClassifyResult` into the
        durable idle bookkeeping, returning the ``PaneSnapshot`` (t1111_4).

        This is the ONLY writer of ``_last_content`` / ``_last_change_time`` and
        must run on the event loop (or synchronously). Generation ownership is the
        caller's job: the sync ``_finalize_capture`` reserved-at-write, the async
        commits (:meth:`commit_snapshot` / :meth:`commit_snapshots`) checked their
        reserved gen before calling here.
        """
        pane_id = pane.pane_id
        prev = self._last_content.get(pane_id)
        if prev is None or result.compare_value != prev:
            self._last_content[pane_id] = result.compare_value
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
            awaiting_input=result.awaiting_input,
            awaiting_input_kind=result.awaiting_input_kind,
            agent_key=result.agent_key,
            scoped=result.scoped,
        )

    def _finalize_capture(
        self, pane: TmuxPaneInfo, content: str
    ) -> PaneSnapshot:
        """Synchronous capture finalize (behind :meth:`capture_pane`, the applink
        router, and sync :meth:`capture_all`).

        Fetch and write are atomic on the loop (no await between), so reservation
        == write instant: it **bumps the generation as it writes**, both marking
        itself the newest capture at that instant and refusing any older in-flight
        async commit (t1111_4). The pure classification is delegated to
        :func:`classify_content`; behaviour (return value + ``_last_content``
        semantics) is unchanged for the direct callers/tests.
        """
        now = time.monotonic()
        mode = self.get_compare_mode(pane.pane_id)
        result = classify_content(
            content, mode, self.prompt_patterns, pane.category,
            agent_key_from_pane(pane.current_command, pane.pane_pid,
                                    pane.pane_id))
        self._next_generation()
        return self._apply_bookkeeping(pane, content, result, now)

    def _capture_args(
        self, pane_id: str, capture_lines: int | None = None
    ) -> list[str]:
        n = self.capture_lines if capture_lines is None else capture_lines
        return [
            "capture-pane", "-p", "-e", "-t", pane_id,
            "-S", f"-{n}",
        ]

    def capture_pane(
        self, pane_id: str, capture_lines: int | None = None
    ) -> PaneSnapshot | None:
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return None
        rc, content = self.tmux_run(self._capture_args(pane_id, capture_lines))
        if rc != 0:
            return None
        return self._finalize_capture(pane, content)

    def get_pane(self, pane_id: str) -> "TmuxPaneInfo | None":
        """Return the cached pane metadata for ``pane_id`` (no subprocess).

        Lightweight accessor over ``_pane_cache`` (populated by discovery) for
        callers that need a pane's ``window_name`` / ``session_name`` without a
        live ``capture-pane`` — e.g. the applink router resolving a pane to its
        task family for the modal handshakes (t822_11). Returns ``None`` when the
        pane is unknown (not yet discovered or already gone).
        """
        return self._pane_cache.get(pane_id)

    def get_shadow_snapshot(self, followed_pane_id: str) -> "PaneSnapshot | None":
        """Latest snapshot of the shadow bound to ``followed_pane_id`` (t1133).

        ``None`` when the agent has no live shadow (or the shadow's capture
        failed this tick). Populated only by the async live path
        (:meth:`commit_snapshots`); the sync :meth:`capture_all` clears the map,
        so a stale value is never returned.
        """
        return self._shadow_snapshots.get(followed_pane_id)

    async def refresh_shadow_snapshot(
        self, followed_pane_id: str
    ) -> "PaneSnapshot | None":
        """Re-capture ONE bound shadow and merge it into the shadow map (t1216_1).

        Lets a caller refresh a single agent's shadow far faster than the ~3 s
        full cycle without paying for (or disturbing) a full refresh. It never
        touches the agent-facing path: no `_next_generation`, no `_pane_cache`
        (the pane object is passed explicitly), no agent snapshots.

        ``None`` means **"no update this tick" — never "the shadow is gone"**.
        There are four such cases and callers must treat them identically,
        leaving whatever is on screen in place:

        1. the followed pane has no shadow entry (nothing to refresh — this
           method never *creates* one, so it can never resurrect a shadow the
           full refresh just removed);
        2. the entry was rebound to a different shadow pane while this capture
           was in flight (see below);
        3. a newer write already landed for this key;
        4. the capture itself failed.

        Only :meth:`commit_snapshots` may DELETE, because only discovery knows
        what actually exists. That asymmetry is deliberate: mirroring the full
        refresh's hide-on-transient-failure at a sub-second cadence would make
        the shadow glyph flicker on any hiccup, so this path retains instead and
        the next full refresh (≤ one refresh interval away) hides or replaces it.
        The staleness that buys is bounded by exactly that interval.

        Two guards make the merge safe against an interleaved full refresh, and
        both run BEFORE any bookkeeping is applied — see
        :meth:`_merge_shadow_snapshot`.
        """
        prev = self._shadow_snapshots.get(followed_pane_id)
        if prev is None:
            return None
        captured_pane_id = prev.pane.pane_id
        # Reserved in the statement immediately before the read below, so the
        # seq orders this write against the full refresh by READ time.
        seq = self._next_shadow_write_seq()
        raw = await self.capture_pane_content_async(captured_pane_id, pane=prev.pane)
        if raw is None:
            return None
        pane, content = raw
        mode = self.get_compare_mode(pane.pane_id)
        patterns = self.prompt_patterns
        result = await self._run_offloaded(
            lambda: _classify_one(
                content, mode, patterns, pane.category,
                agent_key_from_pane(pane.current_command, pane.pane_pid,
                                    pane.pane_id))
        )
        return self._merge_shadow_snapshot(
            followed_pane_id, captured_pane_id, seq, pane, content, result
        )

    def _merge_shadow_snapshot(
        self,
        key: str,
        captured_pane_id: str,
        seq: int,
        pane: TmuxPaneInfo,
        content: str,
        result: "ClassifyResult",
    ) -> "PaneSnapshot | None":
        """Loop-side guarded merge of one re-captured shadow (t1216_1).

        Runs synchronously after the await, so both guards and the write are
        atomic with respect to every other coroutine.

        **Identity, not just existence.** A live shadow can die and be replaced
        by a new one bound to the SAME followed pane while a capture of the old
        one is in flight. The key is still present in that case, so a
        presence-only check would let the dead pane's content overwrite its live
        replacement. Requiring the current entry to still name the pane we
        actually read closes that, and simultaneously covers the removal case.

        **Bookkeeping strictly after the guards.** :meth:`_apply_bookkeeping` is
        the only writer of `_last_content` / `_last_change_time`, and its
        contract puts generation ownership on the caller. Calling it before the
        checks would let a REJECTED late refresh write stale content and reset
        the shadow's idle clock — corrupting state the merge itself then
        declines to publish, and making the next full refresh see a change that
        never happened.
        """
        cur = self._shadow_snapshots.get(key)
        if cur is None or cur.pane.pane_id != captured_pane_id:
            return None  # removed by a full refresh, or rebound to a new shadow
        if seq <= self._shadow_snapshot_seq.get(key, -1):
            return None  # a newer read already landed for this key
        snap = self._apply_bookkeeping(pane, content, result, time.monotonic())
        self._shadow_snapshots[key] = snap
        self._shadow_snapshot_seq[key] = seq
        return snap

    def commit_snapshot(
        self,
        gen: int,
        pane: TmuxPaneInfo,
        content: str,
        result: ClassifyResult,
    ) -> PaneSnapshot | None:
        """Loop-side, generation-guarded single-pane commit (t1111_4).

        Returns ``None`` (writing nothing) when ``gen`` has been superseded by a
        newer reservation — protecting both the idle bookkeeping and the returned
        snapshot. Symmetric with :meth:`commit_snapshots`.
        """
        if gen != self._capture_generation:
            return None
        return self._apply_bookkeeping(pane, content, result, time.monotonic())

    async def capture_pane_async(
        self, pane_id: str, capture_lines: int | None = None
    ) -> PaneSnapshot | None:
        """Finalizing single-pane async capture.

        Reserves its generation **before** the tmux await (its content is "as of"
        fetch-start) and commits guarded, so a stale-but-late return can't clobber
        a newer-reserved refresh (t1111_4). Under no overlap the reserved gen is
        still current at commit → it writes exactly as before (the applink pusher
        test relies on this finalize). Kept for that test / future callers; the
        live refresh paths now use the classified/raw paths instead.
        """
        pane = self._pane_cache.get(pane_id)
        if pane is None:
            return None
        gen = self._next_generation()
        rc, content = await self._tmux_async(self._capture_args(pane_id, capture_lines))
        if rc != 0:
            return None
        mode = self.get_compare_mode(pane_id)
        result = classify_content(
            content, mode, self.prompt_patterns, pane.category,
            agent_key_from_pane(pane.current_command, pane.pane_pid,
                                    pane.pane_id))
        return self.commit_snapshot(gen, pane, content, result)

    async def capture_pane_content_async(
        self, pane_id: str, capture_lines: int | None = None,
        pane: "TmuxPaneInfo | None" = None,
    ) -> tuple["TmuxPaneInfo", str] | None:
        """Raw one-shot capture for consumers (the applink history RPC) that must
        NOT perturb idle/awaiting-input state.

        Returns ``(pane, content)`` or ``None``. Unlike :meth:`capture_pane_async`
        it does **not** call :meth:`_finalize_capture`, so it never touches
        ``_last_content`` / ``_last_change_time`` — idle and prompt detection stay
        driven solely by the live ``capture_all_async`` path. A deeper-than-live
        capture (history pulls ~2000 lines vs the 200-line live capture) would
        otherwise reset the pane's idle clock on every scrollback request.

        ``pane`` (t1133): when the caller already holds the ``TmuxPaneInfo``
        (the shadow-status path — shadow panes are deliberately NOT in
        ``_pane_cache``), pass it to skip the cache lookup. Cache-backed
        callers keep the id-only form.
        """
        if pane is None:
            pane = self._pane_cache.get(pane_id)
        if pane is None:
            return None
        rc, content = await self._tmux_async(self._capture_args(pane_id, capture_lines))
        if rc != 0:
            return None
        return pane, content

    async def capture_pane_classified_async(
        self, pane_id: str, capture_lines: int | None = None
    ) -> tuple[int, "TmuxPaneInfo | None", "str | None", "ClassifyResult | None"]:
        """Two-phase single-pane capture for the fast-preview path (t1111_4).

        Reserves the generation **before** the raw tmux await, offloads the pure
        `classify_content` work, and returns ``(gen, pane, content, result)``
        WITHOUT committing bookkeeping — the caller checks ``gen`` and calls
        :meth:`commit_snapshot` on the loop. On a fetch miss returns
        ``(gen, None, None, None)``. The classify is fail-closed (invariant D).
        """
        gen = self._next_generation()
        raw = await self.capture_pane_content_async(pane_id, capture_lines)
        if raw is None:
            return gen, None, None, None
        pane, content = raw
        mode = self.get_compare_mode(pane_id)
        patterns = self.prompt_patterns
        result = await self._run_offloaded(
            lambda: _classify_one(
                content, mode, patterns, pane.category,
                agent_key_from_pane(pane.current_command, pane.pane_pid,
                                    pane.pane_id))
        )
        return gen, pane, content, result

    async def capture_cursor_async(
        self, pane_id: str
    ) -> tuple[int, int, bool, int] | None:
        """Return the pane cursor as ``(row, col, visible, style)`` or ``None``.

        Used by the applink push loop (t822_8) to populate the ``cursor`` field of
        a ``keyframe`` (``capture-pane`` carries no cursor). ``row``/``col`` are
        the cursor's 0-based position within the visible pane; ``visible`` from
        ``cursor_flag``; ``style`` is block (``0``) in Stage 1 (tmux exposes no
        portable cursor-shape field here).
        """
        rc, out = await self._tmux_async([
            "display-message", "-p", "-t", pane_id,
            "-F", "#{cursor_y} #{cursor_x} #{cursor_flag}",
        ])
        if rc != 0:
            return None
        parts = out.strip().split()
        if len(parts) < 3:
            return None
        try:
            return (int(parts[0]), int(parts[1]), parts[2] == "1", 0)
        except ValueError:
            return None

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
        """Synchronous all-pane capture (debug CLI `tmux_monitor.py` only).

        Agent-facing panes only — shadow-status state (t1133) is produced
        solely by the async live path (`capture_all_classified_async` →
        `commit_snapshots`). This path CLEARS `_shadow_snapshots` so a sync
        cycle can never leave stale shadow state visible behind
        `get_shadow_snapshot`: the glyph goes absent, never frozen.
        """
        panes = self.discover_panes()
        self._clean_stale({p.pane_id for p in panes})
        self._clear_shadow_snapshots()

        snapshots: dict[str, PaneSnapshot] = {}
        for pane in panes:
            snap = self.capture_pane(pane.pane_id)
            if snap is not None:
                snapshots[pane.pane_id] = snap
        return snapshots

    async def capture_all_classified_async(
        self,
    ) -> tuple[int, list[tuple[TmuxPaneInfo, "str | None", "ClassifyResult | None"]]]:
        """Offloadable produce phase of the live refresh (t1111_4).

        Reserves the generation, discovers panes, does the raw (non-finalizing)
        captures concurrently, then runs ONE off-loop batch of `classify_content`
        (the strip/prompt-regex CPU work). Returns ``(gen, classified)`` where each
        entry is ``(pane, content, result)`` for a successful capture and
        ``(pane, None, None)`` for a pane whose raw fetch failed — the failed
        pane's id is still present so the loop-side :meth:`commit_snapshots` can
        clean stale ids without dropping a pane over a transient capture error.
        Mutates **no** ``_last_content`` state; that is the commit's job.

        The shadow WRITE seq is reserved further down — **after** discovery and
        immediately before the raw-capture gather — not here beside ``gen``. See
        the comment at that site (t1216_1).
        """
        gen = self._next_generation()
        # Caller-owned sink: the enumerated-session set belongs to THIS call, so
        # an overlapping discovery cannot hand its answer to our generation.
        enum_sink: list = []
        panes, shadows = await self.discover_panes_with_shadows_async(
            enum_sink=enum_sink
        )

        # Discovery-derived liveness facts, stamped with THIS generation
        # (t1326). Recorded here — from discovery — and never from the committed
        # snapshots, because `commit_snapshots` drops any pane whose content
        # capture failed (`if result is None: continue`). Deriving "which agents
        # exist" from snapshots would make a transient capture failure look like
        # a departed agent, and the mark purge would delete a live agent's mark.
        #
        # Keyed by `gen` rather than assigned to a bare attribute so an older
        # overlapping capture can never overwrite a newer one's facts: the
        # winning commit pops its own key, and losing generations are pruned.
        self._record_discovery_facts(
            gen, panes, shadows,
            enum_sink[0] if enum_sink else None,
        )

        # Raw captures concurrently (non-finalizing); tolerate per-pane faults.
        # Shadow panes (t1133) join the SAME gather (invariant E — one cycle,
        # no separate fan-out); they pass their pane object explicitly because
        # they are never in `_pane_cache` (cache-boundary invariant).
        all_panes = panes + shadows
        # Reserve this batch's shadow WRITE seq HERE — after the discovery await
        # above, in the last statement before the shadow panes are actually read
        # (t1216_1). Reserving it beside `gen` would date this batch from before
        # discovery, so a fast `refresh_shadow_snapshot` that both reserved AND
        # read entirely inside the discovery window would out-rank a full refresh
        # that reads the same pane later — and the full refresh's NEWER content
        # would lose the merge. The `gen ==` guard stops a batch that has already
        # been superseded from clobbering the live batch's reservation (it cannot
        # commit anyway — `commit_snapshots` rejects it at the same check).
        if gen == self._capture_generation:
            self._full_shadow_seq = (gen, self._next_shadow_write_seq())
        raw_results = await asyncio.gather(
            *(self.capture_pane_content_async(p.pane_id, pane=p) for p in all_panes),
            return_exceptions=True,
        )

        # Read per-pane mode on the loop (invariant B) and assemble the batch.
        to_classify: list[tuple[TmuxPaneInfo, str, str]] = []
        failed: list[TmuxPaneInfo] = []
        for pane, res in zip(all_panes, raw_results):
            if isinstance(res, tuple):
                _, content = res
                to_classify.append((pane, content, self.get_compare_mode(pane.pane_id)))
            else:
                # None (fetch miss) or an Exception (fault): keep prior content.
                failed.append(pane)

        patterns = self.prompt_patterns  # read on loop, passed by value
        classified_ok = await self._run_offloaded(
            lambda: _classify_batch(to_classify, patterns)
        )
        classified: list[tuple[TmuxPaneInfo, str | None, ClassifyResult | None]] = list(
            classified_ok
        )
        classified.extend((pane, None, None) for pane in failed)
        return gen, classified

    def commit_snapshots(
        self,
        gen: int,
        classified: list[tuple[TmuxPaneInfo, "str | None", "ClassifyResult | None"]],
    ) -> dict[str, PaneSnapshot] | None:
        """Loop-side, generation-guarded commit of a produced batch (t1111_4).

        Returns ``None`` (touching nothing — idle clock AND returned set both
        protected) when ``gen`` has been superseded by a newer reservation.
        Otherwise cleans stale panes and applies the idle bookkeeping, returning
        the assembled snapshots. Panes whose raw fetch failed (``result is None``)
        are kept in the clean-stale set but produce no snapshot this tick, so their
        prior ``_last_content`` survives — matching the pre-split behaviour.

        Shadow split (t1133): entries whose ``pane.shadow_target`` is non-empty
        are committed into a **fresh** ``_shadow_snapshots`` map (keyed by the
        FOLLOWED pane's id) instead of the returned dict, so shadow panes never
        surface in agent-facing snapshots. Rebuilt-wholesale semantics: a dead
        shadow disappears next tick, and a shadow whose raw fetch transiently
        failed produces no entry this tick (glyph hidden for the tick — the
        same one-tick dropout a failed agent pane's row has; deliberately no
        stale-state preservation, which would freeze the idle clock on screen).
        Duplicate shadows targeting one followed pane: the newest (largest
        ``%N``) wins, mirroring ``match_shadow_pane``.

        Stamped merge (t1216_1): "rebuilt wholesale" now means *rebuilt for every
        key this batch is the newest reader of*. Each rebuilt entry carries the
        shadow WRITE seq this batch reserved at its capture site, and a key that
        an interleaved :meth:`refresh_shadow_snapshot` read **later** keeps the
        refresh's entry — but only while both are reads of the *same* pane, since
        discovery, not the seq, decides WHICH pane is a given agent's shadow.
        Deletion is unchanged and remains exclusive to this method: a key absent
        from this batch's own discovery is dropped regardless of seq, which is
        what makes a dead shadow disappear and what the single-shadow merge
        relies on to never resurrect one.
        """
        if gen != self._capture_generation:
            return None
        # Past the guard: this generation won, so promote the discovery facts it
        # recorded (t1326). Doing it here — atomically with the snapshots — is
        # what guarantees the mark purge can never pair one tick's snapshots
        # with another tick's view of which sessions and agents exist.
        self._publish_discovery_facts(gen)
        self._clean_stale({pane.pane_id for pane, _, _ in classified})
        # Cache-boundary enforcement (t1133): a shadow pane discovered BEFORE
        # its `@aitask_shadow_target` option was stamped (the spawner sets it
        # after the pane exists) may have been cached as a normal agent on that
        # earlier tick — and `_clean_stale` keeps it because the shadow id is
        # in the classified keep-set. Evict such entries from every
        # cache-backed map here (loop-side), so `get_pane`/`capture_pane`/
        # compare-mode state stay shadow-blind even across that race.
        # (`_last_content`/`_last_change_time` deliberately keep shadow ids —
        # that is the shadow's idle bookkeeping.)
        for pane, _, _ in classified:
            if pane.shadow_target:
                self._pane_cache.pop(pane.pane_id, None)
                self._compare_mode_overrides.pop(pane.pane_id, None)
        now = time.monotonic()
        snapshots: dict[str, PaneSnapshot] = {}
        # Shadow entries are only SELECTED here; their bookkeeping is deferred
        # until after the per-key merge below has picked a winner. Agent panes
        # are unaffected and keep their bookkeeping inline.
        #
        # Why: `_apply_bookkeeping` is the sole writer of `_last_content` /
        # `_last_change_time`, and the merge can retain a newer fast-refresh
        # snapshot for a key. Applying it to a batch shadow that then LOSES the
        # merge would leave the displayed snapshot new while rewriting the idle
        # bookkeeping with this batch's older content — so the next full refresh
        # would see a change that never happened and reset the idle clock. Same
        # ordering rule `_merge_shadow_snapshot` follows: decide first, write
        # bookkeeping only for the entry actually published.
        shadow_candidates: dict[
            str, tuple[TmuxPaneInfo, str, "ClassifyResult"]
        ] = {}
        for pane, content, result in classified:
            if result is None:
                continue
            if pane.shadow_target:
                prev = shadow_candidates.get(pane.shadow_target)
                if prev is None or (
                    _pane_id_num(pane.pane_id) > _pane_id_num(prev[0].pane_id)
                ):
                    shadow_candidates[pane.shadow_target] = (pane, content, result)
            else:
                snapshots[pane.pane_id] = self._apply_bookkeeping(
                    pane, content, result, now
                )
        # Stamp this batch with the seq reserved at its capture site. The
        # fallback covers a hand-built `commit_snapshots` call with no matching
        # `capture_all_classified_async` reservation: a fresh (therefore highest)
        # seq reproduces the pre-t1216_1 wholesale-overwrite semantics exactly.
        if self._full_shadow_seq is not None and self._full_shadow_seq[0] == gen:
            batch_seq = self._full_shadow_seq[1]
        else:
            batch_seq = self._next_shadow_write_seq()
        # Discovery is authoritative for EXISTENCE and IDENTITY (which pane is
        # this agent's shadow); the seq arbitrates only RECENCY, and only between
        # two reads of the SAME pane. So a key an interleaved single-shadow
        # refresh read later keeps that refresh's newer entry — unless discovery
        # has since bound a different pane to the key, in which case the newer
        # read is of a pane that is no longer the shadow and must not be kept.
        # (This is the commit-side half of the rebind race that
        # `_merge_shadow_snapshot` guards from the other direction.)
        merged: dict[str, PaneSnapshot] = {}
        merged_seq: dict[str, int] = {}
        for key, (pane, content, result) in shadow_candidates.items():
            prior_seq = self._shadow_snapshot_seq.get(key)
            prior_snap = self._shadow_snapshots.get(key)
            if (
                prior_seq is not None
                and prior_snap is not None
                and prior_snap.pane.pane_id == pane.pane_id
                and prior_seq > batch_seq
            ):
                # This batch lost: leave both the snapshot AND the idle
                # bookkeeping exactly as the newer read left them.
                merged[key] = prior_snap
                merged_seq[key] = prior_seq
            else:
                merged[key] = self._apply_bookkeeping(pane, content, result, now)
                merged_seq[key] = batch_seq
        self._shadow_snapshots = merged
        self._shadow_snapshot_seq = merged_seq
        return snapshots

    async def capture_all_async(self) -> dict[str, PaneSnapshot] | None:
        """Live all-pane capture with the classify CPU work off the event loop.

        Returns the snapshot dict, or ``None`` when a newer overlapping
        `capture_all_async` (or other capture) reserved a later generation before
        this one committed — the caller MUST skip applying a ``None`` so a stale
        cycle can neither corrupt ``_last_content`` nor overwrite the caller's
        visible snapshots (t1111_4). For a serial caller ``gen`` is always current
        → a dict, behaviourally identical to the pre-split path.
        """
        gen, classified = await self.capture_all_classified_async()
        return self.commit_snapshots(gen, classified)

    def send_enter(self, pane_id: str) -> bool:
        # `--` ends option parsing so a hostile pane_id/key can't be read as a
        # tmux flag (defense-in-depth; pane_id is already the -t value).
        rc, _ = self.tmux_run(["send-keys", "-t", pane_id, "--", "Enter"])
        return rc == 0

    def send_keys(self, pane_id: str, keys: str, literal: bool = False) -> bool:
        """Send arbitrary key(s) to a tmux pane.

        If literal=True, uses -l flag to send raw text without interpretation.
        If literal=False, sends as tmux key name (Enter, Up, C-c, etc.).
        """
        cmd = ["send-keys", "-t", pane_id]
        if literal:
            cmd.append("-l")
        # `--` ends option parsing: without it a leading-dash `keys` value (e.g.
        # "-R", "-N") is consumed by tmux as a flag rather than sent as keys.
        cmd.append("--")
        cmd.append(keys)
        rc, _ = self.tmux_run(cmd)
        return rc == 0

    def forward_key(
        self, pane_id: str, key: str, character: str | None = None
    ) -> bool:
        """Translate an abstract key name and forward it to a tmux pane.

        Backs both the desktop preview-zone key forwarding and the applink
        ``forward_key`` verb (t822_7). Returns ``False`` when the key is
        unmappable (no tmux equivalent).
        """
        translated = translate_key(key, character)
        if translated is None:
            return False
        keys, literal = translated
        return self.send_keys(pane_id, keys, literal=literal)

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
        rc, stdout = self.tmux_run([
            "list-panes", "-t", window_target,
            "-F", "#{pane_id}\t#{pane_pid}\t#{@aitask_shadow_target}",
        ])
        if rc != 0:
            return self.kill_pane(pane_id), False
        records: list[tuple[str, bool]] = []
        for line in stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            other_id, pid_str, shadow_target = parts
            try:
                pid = int(pid_str)
            except ValueError:
                continue
            # A pane is a helper (does NOT keep the window alive) when it is a
            # companion (minimonitor/monitor) OR a shadow bound to an agent.
            is_helper = is_shadow_target(shadow_target) or _is_companion_process(pid)
            records.append((other_id, is_helper))
        others = count_other_real_agents(records, pane_id)

        if others == 0:
            return self.kill_window(pane_id), True
        return self.kill_pane(pane_id), False

    def spawn_tui(self, tui_name: str) -> bool:
        # SECURITY (t985): tmux `new-window`'s last arg is a shell command, so an
        # unconstrained tui_name interpolated into f"ait {tui_name}" is arbitrary
        # command execution. Refuse anything not in the canonical TUI registry
        # (TUI_NAMES) BEFORE it reaches the shell — closes the sink for every
        # caller (desktop monitor + applink). Valid spawns derive from the same
        # registry, so legitimate launches are unaffected.
        if tui_name not in TUI_NAMES:
            return False
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


def load_project_tmux_config(project_root: Path) -> dict:
    """Load the ``tmux`` section from project_config.yaml.

    Companion to :func:`load_monitor_config` (which returns the nested
    ``tmux.monitor`` subsection). Shared by both monitor apps so the shadow
    placement keys (``shadow_same_window``, ``shadow_pane_width``,
    ``default_split``) are read identically (t1216_4).
    """
    try:
        import yaml
        pc = project_root / "aitasks" / "metadata" / "project_config.yaml"
        if pc.is_file():
            with open(pc) as f:
                data = yaml.safe_load(f) or {}
            return data.get("tmux", {})
    except Exception:
        pass
    return {}


def spawn_shadow(
    monitor,
    *,
    full_cmd: str,
    followed_pane: str,
    followed_window: str,
    session: str,
    task_id: str | None,
    target_root: Path,
    companion_pane: str | None,
    select_window: bool,
    notify: Callable[..., None],
    schedule_refresh: Callable[[], None],
    phase_signal=None,
) -> str | None:
    """Place, launch, and lifecycle-wire a shadow companion pane.

    Shared body behind both apps' ``e`` / ``E`` shortcuts (t1216_4). Placement is
    ALWAYS handler-controlled — a same-window split to the RIGHT of the followed
    AGENT pane sized to ``shadow_pane_width``, or a separate window when
    ``tmux.shadow_same_window`` is false — never a picker dialog's own placement.
    Returns the new shadow's pane id, or ``None`` when nothing usable was created.

    ``monitor`` is duck-typed on the **gateway surface only** (``tmux_run`` ->
    ``(rc, stdout)``), matching the rest of this module's shadow seam; the
    ``notify`` / ``schedule_refresh`` callables keep it Textual-free.

    **This function never reads ``TMUX_PANE``.** ``companion_pane`` is the pane
    ``aitask_companion_cleanup.sh`` despawns once the followed agent's window
    holds no real agent besides the dying one; ``None`` means "bind to the newly
    created shadow pane", which is always safe. Pass a pane **outside** the
    followed agent's window only if you want that pane killed on the agent's
    death — the script's job-2 ``kill-pane`` has no marker check, so passing a
    monitor's own pane makes the agent's exit close the monitor. Callers state
    this as per-app policy; there is no default.

    ``schedule_refresh`` is **not** called when the launch itself fails, so a
    failed spawn does not trigger a redundant refresh.

    If the ``@aitask_shadow_target`` stamp cannot be written the new pane is
    killed rather than left behind: an unstamped shadow is indistinguishable from
    a real agent forever (it lists as an agent, is targeted by kill/next-agent
    actions, counts as a real sibling, evades the duplicate guard, and — because
    the cleanup script matches on the marker — is never cleaned up).
    """
    if monitor is None:
        return None
    # Placement: same window (split) by default; separate window if the project
    # config opts out.
    tmux_cfg = load_project_tmux_config(target_root)
    same_window = bool(tmux_cfg.get("shadow_same_window", True))
    if same_window:
        try:
            shadow_width = int(tmux_cfg.get("shadow_pane_width", 60))
        except (TypeError, ValueError):
            shadow_width = 60
        cfg = TmuxLaunchConfig(
            session=session,
            window=followed_window,
            new_session=False,
            new_window=False,
            split_direction=str(tmux_cfg.get("default_split", "horizontal")),
            # Insert the shadow to the RIGHT of the followed AGENT pane, sized to
            # the configured width (t994). Target the agent pane (not the
            # window's active pane, which may be a narrow minimonitor) so the
            # width is sized against the wide agent pane; keep the agent anchored
            # on the left (no split_before).
            split_size=shadow_width,
            split_target_pane=followed_pane,
            cwd=str(target_root),
            select_window=select_window,
        )
    else:
        cfg = TmuxLaunchConfig(
            session=session,
            window=f"agent-shadow-{task_id or 'x'}",
            new_session=False,
            new_window=True,
            cwd=str(target_root),
            select_window=select_window,
        )

    # Last-moment duplicate re-check. The callers' pre-dialog guard cannot cover
    # the seconds an agent-picker dialog is open, nor two queued dialogs. Refuse
    # on a found shadow AND on an unverifiable query — spawning a second shadow
    # breaks the one-shadow-per-agent lifecycle binding.
    ok, existing = find_shadow_pane_status(monitor, followed_pane)
    if not ok:
        notify(
            "Could not verify whether a shadow is already running — not launching",
            severity="warning",
        )
        return None
    if existing:
        notify("A shadow is already running for this agent", severity="warning")
        return None

    pane_pid, err = launch_in_tmux(full_cmd, cfg)
    if err:
        notify(f"Shadow launch failed: {err}", severity="error")
        return None

    # Resolve the new shadow pane id from its pid and stamp the authoritative
    # @aitask_shadow_target option. Without it a same-window shadow (sharing the
    # agent's window name) would be listed as an agent and never auto-killed.
    shadow_pane = resolve_pane_id_by_pid(session, pane_pid) if pane_pid else None
    if not shadow_pane:
        notify(
            "Shadow launched, but its pane could not be classified "
            "— it may appear in the agent list",
            severity="warning",
        )
        schedule_refresh()
        return None

    stamp_args = ["set-option", "-p", "-t", shadow_pane,
                  SHADOW_TARGET_OPTION, followed_pane]
    rc, _ = monitor.tmux_run(stamp_args)
    if rc != 0:
        rc, _ = monitor.tmux_run(stamp_args)
    if rc != 0:
        # We own this pane and it is milliseconds old; leaving it unstamped is
        # strictly worse than removing it.
        monitor.tmux_run(["kill-pane", "-t", shadow_pane])
        notify(
            f"Shadow pane {shadow_pane} could not be classified — removed it. "
            "No shadow is running.",
            severity="error",
        )
        schedule_refresh()
        return None

    # Ensure the followed agent auto-kills its bound shadow on exit.
    hook_status = attach_companion_cleanup_hook(
        followed_pane, companion_pane or shadow_pane
    )
    if hook_status == "unverified":
        notify(
            "Shadow launched; auto-cleanup on agent exit could not be wired "
            "— close the shadow by hand when the agent exits",
            severity="warning",
        )
    else:
        notify("Launched shadow agent")
    # Stamp the advisory phase BEFORE handing control back (t1420). The per-tick
    # re-stamp is not sufficient on its own: the user can launch a shadow and
    # have it read `--phase` before the next UI tick, and it would then miss the
    # very checkpoint they spawned it for and fall back to the ledger. Callers
    # pass the signal because only they hold the followed pane's live half.
    # Best-effort by contract — see refresh_shadow_phase_stamp.
    if phase_signal is not None:
        refresh_shadow_phase_stamp(monitor, shadow_pane, phase_signal)
    schedule_refresh()
    return shadow_pane


def refresh_shadow_phase_stamp(monitor, shadow_pane: str, signal) -> bool:
    """Write the advisory phase onto a shadow pane's ``@aitask_shadow_phase``.

    Shared rather than living in one app: **both** TUIs spawn shadows
    (``minimonitor_app.action_launch_shadow`` and
    ``monitor_app.action_launch_shadow``), so a refresh wired into only one would
    leave the other's shadows frozen at their launch value — exactly the
    staleness the pane-option channel was chosen over argv to avoid. Callers pass
    it from whatever per-tick path already resolved a bound shadow pane; the
    comparison/mutation lives here and the display stays theirs, the same split
    :func:`compute_shadow_staleness` uses.

    **Best-effort, and deliberately NOT fatal** — the opposite of the
    ``@aitask_shadow_target`` stamp in :func:`spawn_shadow`, which kills the pane
    when it fails because an unclassifiable shadow is worse than none. An
    advisory hint must never be able to destroy or disturb a shadow, so every
    failure here is swallowed and the previous value simply stands.
    """
    if not shadow_pane or signal is None:
        return False
    # Built OUTSIDE the guard on purpose. ``format_signal`` is total — it
    # validates every field against its vocabulary and cannot raise on a
    # PhaseSignal — so anything that blows up here is a programming error, and a
    # broad ``except`` around it would turn that into a silent no-op. (It did
    # exactly that once: a missing SHADOW_PHASE_OPTION became a swallowed
    # NameError and the stamp never wrote, with every test still green.)
    line = workflow_phase.format_signal(signal)
    args = ["set-option", "-p", "-t", shadow_pane, SHADOW_PHASE_OPTION, line]
    try:
        rc, _ = monitor.tmux_run(args)
    except Exception:
        # Only the transport is tolerated: tmux may be gone, the pane may have
        # died between resolution and write, or a duck-typed monitor may raise.
        return False
    return rc == 0


# -- Task context --------------------------------------------------------------

_TASK_ID_RE = re.compile(r'^agent-(?:pick|qa|resume)-(\d+(?:_\d+)?)$')


def task_id_from_window_name(window_name: str) -> str | None:
    """Pure pane→task mapping: extract the task id from an agent window name.

    Returns the captured id (e.g. ``"100"`` or ``"100_1"``) or ``None`` when the
    window name is not an ``agent-(pick|qa|resume)-<id>`` window. Kept
    import-free and side-effect-free so it can be unit-tested directly.

    ``resume`` was added in t1322: the board launches resumed agents into
    ``agent-resume-<id>`` windows, which previously matched nothing — so a
    resumed agent showed no task title, no gate summary, and could never reach
    the COMPLETED status. Prefixes that carry no task id (``agent-explore-``,
    ``agent-raw-``) must keep resolving to ``None``.
    """

    m = _TASK_ID_RE.match(window_name)
    return m.group(1) if m else None


@dataclass
class TaskInfo:
    """Resolved task metadata and content for display in the monitor."""
    task_id: str
    task_file: str
    title: str
    priority: str
    effort: str
    issue_type: str
    status: str
    body: str
    plan_content: str | None
    # Absolute path to the task file. ``task_file`` stays relative to the owning
    # project root (display value, asserted by tests); ``task_file_abs`` is what
    # gate-ledger parsing must use, since a relative path is cwd-dependent and
    # wrong under cross-session / multi-project monitoring. Defaulted so the one
    # keyword-arg test stub keeps constructing TaskInfo unchanged.
    task_file_abs: str = ""
    # Normalized ``depends`` ids (bare, a leading ``t`` stripped) — the same
    # normalization ``find_ready_siblings`` applies. Feeds
    # :meth:`TaskInfoCache.blocking_dependencies`, which the minimonitor's
    # pick-by-number dialog uses to warn about an unpickable target (t1310).
    # Defaulted for the same reason as ``task_file_abs``.
    depends: list[str] = field(default_factory=list)
    # File identity ``(st_mtime_ns, st_size)`` of ``task_file_abs``, sampled
    # BEFORE the content read in ``_resolve`` — never after (t1322). The archive
    # script's rewrites are rename-based (``sed -i``, ``awk > tmp && mv`` in
    # aitask_archive.sh), so a read that races a rewrite returns the OLD inode's
    # bytes while a post-read stat samples the NEW one — which would pin stale
    # content under a fresh key, permanently. ``None`` (unstat-able, or a
    # hand-built test stub) means "never serve this from cache".
    file_identity: tuple[int, int] | None = None


def _file_identity(path: str) -> tuple[int, int] | None:
    """``(st_mtime_ns, st_size)`` for ``path``, or ``None`` if it cannot be stat'ed.

    ns mtime (not float ``st_mtime``) catches two edits inside one wall-clock
    second; ``st_size`` closes the same-mtime-different-length case. Deliberately
    the same key :class:`GateSummaryCache` uses, so two caches over the same file
    can never disagree about whether it changed.
    """
    if not path:
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


class GateSummaryCache:
    """Compact gate-summary cache for the monitor TUIs.

    Invalidated by file identity (``(st_mtime_ns, st_size)`` of the task file)
    rather than a per-tick ``clear()``: a live-growing ledger re-derives only on
    the tick its file actually changes, so an unchanged ledger is never re-read
    from disk. (The board's ``aitask_board.TaskManager.gate_state_for`` clears
    each cycle; keying on mtime here removes that per-tick disk I/O.) Fails
    closed to ``""`` (no column) on any parse/IO error — a malformed or missing
    ledger must never break the monitor. Keyed by the resolved **absolute**
    task-file path (``TaskInfo.task_file_abs``), so it is correct under
    cross-session / multi-project monitoring regardless of the process's working
    directory.

    ``clear()`` is retained for minimonitor, which still clears each refresh.

    **Also carries the ledger half of the workflow-phase signal (t1420).** The
    full ``TaskGateState`` was already being derived here and thrown away; the
    phase seam extends this cache's stored value rather than adding a second
    parse of the same file (the t1323 seam). Only the FILE-derived half is
    cached — its key is file identity, whereas the live half changes every tick,
    so :meth:`phase_for` composes that at call time.
    """

    def __init__(self) -> None:
        # abs task-file path -> ((st_mtime_ns, st_size), summary,
        #                        (phase, detail), (recording, detail)).
        self._cache: dict[
            str, tuple[tuple[int, int], str, tuple[str, str], tuple[str, str]]
        ] = {}

    def clear(self) -> None:
        self._cache.clear()

    def summary_for(self, info: "TaskInfo | None") -> str:
        return self._entry_for(info)[0]

    def ledger_phase_for(self, info: "TaskInfo | None") -> tuple[str, str]:
        """``(phase, detail)`` — the file-derived half of the phase signal."""
        entry = self._entry_for(info)
        return entry[1]

    def phase_for(self, info: "TaskInfo | None", *,
                  screen_text: str | None = None,
                  awaiting_input: bool | None = None,
                  awaiting_input_kind: str = "",
                  agent: str = "",
                  current_command: str | None = None
                  ) -> "workflow_phase.PhaseSignal":
        """Compose the cached ledger half with this tick's live observation.

        Advisory only: the returned phase may never gate what a caller does.

        ``agent`` should be the key that actually scoped the pane's prompt
        matching (``PaneSnapshot.agent_key``); pass ``current_command`` alongside
        it so an unresolvable pane is reported as such rather than as a caller
        that supplied nothing (t1467).
        """
        entry = self._entry_for(info)
        return workflow_phase.compose(
            entry[1], screen_text=screen_text, awaiting_input=awaiting_input,
            awaiting_input_kind=awaiting_input_kind, agent=agent,
            recording=entry[2], current_command=current_command)

    def _entry_for(
        self, info: "TaskInfo | None"
    ) -> tuple[str, tuple[str, str], tuple[str, str]]:
        # Key + parse off the ABSOLUTE path, never the relative ``task_file`` —
        # the relative form is cwd-dependent and resolves wrong in cross-session
        # monitor mode.
        _EMPTY = ("", (workflow_phase.UNKNOWN_PHASE, "no task file"),
                  ("unknown", ""))
        if info is None or not info.task_file_abs:
            return _EMPTY
        key = info.task_file_abs
        # File-identity key: ns mtime + size. ns granularity (not float
        # ``st_mtime``) catches two ledger edits within the same wall-clock
        # second; size closes the same-mtime-different-length case cheaply.
        # A missing/unreadable file is a miss that fails closed to ``""``.
        try:
            st = os.stat(key)
        except OSError:
            self._cache.pop(key, None)
            return _EMPTY
        identity = (st.st_mtime_ns, st.st_size)
        cached = self._cache.get(key)
        if cached is not None and cached[0] == identity:
            return cached[1], cached[2], cached[3]
        summary = ""
        # Derived from the already-loaded body, so an unreadable path still
        # yields an honest UNKNOWN rather than a fabricated PLAN (t1420).
        phase = workflow_phase.phase_from_ledger_text(info.body or "")
        recording = ("unknown", "")
        try:
            # Cheap prefilter on the already-loaded body before the full parse;
            # the full state re-reads the file (matches the board: has_ledger
            # from content, state from filepath).
            if gate_ledger.has_gate_markers(info.body or ""):
                state = gate_ledger.read_task_gate_state(info.task_file_abs)
                summary = gate_ledger.compact_gate_summary(state)
        except Exception:
            summary = ""
        try:
            recording = workflow_phase.recording_from_text(
                info.body or "",
                workflow_phase.default_profiles_dir(info.task_file_abs))
        except Exception:
            recording = ("unknown", "")
        self._cache[key] = (identity, summary, phase, recording)
        return summary, phase, recording


@dataclass
class _TaskEntry:
    """One :class:`TaskInfoCache` slot.

    A positive entry carries its own freshness key on ``info.file_identity``; a
    negative one has no path to stat, so it carries a retry budget instead.
    """
    info: TaskInfo | None
    miss_at: float = 0.0     # monotonic time of the last failed _resolve
    miss_count: int = 0      # consecutive failed _resolves


class TaskInfoCache:
    """Cache for resolved task info — avoids file I/O on every refresh.

    Cross-project aware: when callers provide a tmux ``session_name`` the cache
    resolves the task file from the project root that owns that session (via
    ``session_to_project``). An empty/unknown ``session_name`` falls back to
    the local ``project_root`` — preserving single-session behaviour.

    **Freshness (t1322).** Entries are invalidated by file identity
    (``(st_mtime_ns, st_size)``), the same key :class:`GateSummaryCache` uses.
    Before t1322 a resolved entry was immortal: a task archived while the TUI was
    open served its pre-archival ``TaskInfo`` forever, which made a COMPLETED
    status impossible to detect. Three things now reject a cached answer:

    * the identity changed — an in-place edit (``status: Ready`` → ``Done``);
    * the stat raised — the file **moved** (``aitasks/`` → ``aitasks/archived/``);
    * the entry is negative and its retry is due (see ``_MISS_RETRY_SCHEDULE``).

    Unlike :class:`GateSummaryCache`, an ``OSError`` here must **re-resolve, not
    fail closed**: failing closed would blank the pane's task title on exactly
    the tick its task completes.
    """

    # Backoff steps for a negative (unresolvable) entry, then a sparse terminal
    # interval repeated FOREVER. The terminal step is load-bearing: a budget
    # that stops permanently poisons a pane whose miss outlived it — an
    # interrupted archive, or a long `.aitask-data` reconciliation holding
    # `aitasks/` unresolvable for minutes — and nothing else guarantees
    # recovery. Steady-state cost is one _resolve per 5 min per missing task.
    _MISS_RETRY_SCHEDULE: tuple[float, ...] = (5.0, 15.0, 60.0)
    _MISS_RETRY_TERMINAL: float = 300.0

    # Injectable clock so tests drive the retry schedule deterministically
    # instead of monkeypatching time.monotonic globally (no sleeps — see
    # aidocs/framework/testing_conventions.md).
    _now = staticmethod(time.monotonic)

    def __init__(
        self,
        project_root: Path,
        session_to_project: dict[str, Path] | None = None,
    ):
        self._project_root = project_root
        self._session_to_project: dict[str, Path] = dict(session_to_project or {})
        # Keyed by (session_name, task_id) so two projects can both have t100
        # without clobbering each other.
        self._cache: dict[tuple[str, str], _TaskEntry] = {}
        self._window_to_task_id: dict[str, str | None] = {}
        # Pane-keyed task-id cache (t986). Keyed by pane_id so panes sharing a
        # window are never conflated; see get_task_id_for_pane.
        self._pane_to_task_id: dict[str, str | None] = {}

    def update_session_mapping(self, mapping: dict[str, Path]) -> None:
        """Replace the session→project_root mapping (idempotent).

        Clears the resolved-task cache when the mapping changes, since entries
        for a session may have been resolved against a stale (or absent)
        mapping and now point at the wrong project's task data.

        **Do not delete this as redundant now that entries are identity-keyed
        (t1322).** It is the one staleness class the identity key structurally
        cannot catch: when a session's project root changes, the OLD root's
        absolute path may still stat perfectly fine (a real ``t100`` in the
        fallback project), so the identity gate would keep serving the wrong
        project's task indefinitely, with no signal. Clearing also resets the
        negative-retry budgets — correct, since a mapping change is exactly the
        event that can turn a permanent miss into a hit.
        """
        if mapping != self._session_to_project:
            self._session_to_project = dict(mapping)
            self._cache.clear()

    def _root_for_session(self, session_name: str) -> Path:
        """Resolve the project root for a tmux session, falling back to local."""
        if session_name and session_name in self._session_to_project:
            return self._session_to_project[session_name]
        return self._project_root

    def get_task_id(self, window_name: str) -> str | None:
        """Extract task ID from agent window name. Cached.

        Window-keyed; retained for callers that only have a window name. Pane
        display sites should prefer :meth:`get_task_id_for_pane`.
        """
        if window_name not in self._window_to_task_id:
            self._window_to_task_id[window_name] = task_id_from_window_name(window_name)
        return self._window_to_task_id[window_name]

    def get_task_id_for_pane(self, pane: TmuxPaneInfo) -> str | None:
        """Resolve the task id for a specific pane, cached by ``pane_id``.

        Pane-keyed rather than window-keyed (t986): a tmux window may hold more
        than one pane (an agent plus a shadow/minimonitor helper, or — in
        future — more than one agent), so conflating panes by their shared
        window name is unsafe. The task id is still *derived* from the agent
        window name today; keying the cache on ``pane_id`` is the seam a future
        per-pane task source can slot into without touching call sites. Helper
        panes do not reach this method (discovery already drops shadow/companion
        panes), and a stray helper window name resolves to ``None`` anyway.
        """
        pane_id = pane.pane_id
        if pane_id not in self._pane_to_task_id:
            self._pane_to_task_id[pane_id] = task_id_from_window_name(pane.window_name)
        return self._pane_to_task_id[pane_id]

    def get_task_info(
        self, task_id: str, session_name: str = ""
    ) -> TaskInfo | None:
        """Resolve task info from task ID, re-reading when the file changed.

        Hot path is exactly one ``os.stat`` on the cached ``task_file_abs``
        (~0.65 µs warm, vs ~125 µs for a full re-resolve), so an unchanged task
        is never re-read from disk. See the class docstring for the three ways a
        cached answer is rejected.
        """
        key = (session_name, task_id)
        entry = self._cache.get(key)
        if entry is not None:
            info = entry.info
            if info is not None:
                # The `is not None` guard is load-bearing: _file_identity
                # returns None on OSError, and a bare `==` would make
                # None == None true — serving a stale entry for a file we can
                # no longer stat, which is precisely the archived-move case.
                if (
                    info.file_identity is not None
                    and _file_identity(info.task_file_abs) == info.file_identity
                ):
                    return info
            elif not self._miss_retry_due(entry):
                return None
        return self._store(key, self._resolve(task_id, session_name), entry)

    def _miss_retry_due(self, entry: _TaskEntry) -> bool:
        """Whether a negative entry is due for another ``_resolve`` attempt.

        Backs off through ``_MISS_RETRY_SCHEDULE`` and then repeats
        ``_MISS_RETRY_TERMINAL`` forever — it never stops retrying.
        """
        idx = entry.miss_count - 1
        if idx < len(self._MISS_RETRY_SCHEDULE):
            step = self._MISS_RETRY_SCHEDULE[idx]
        else:
            step = self._MISS_RETRY_TERMINAL
        return (self._now() - entry.miss_at) >= step

    def _store(
        self,
        key: tuple[str, str],
        info: TaskInfo | None,
        prev: _TaskEntry | None,
    ) -> TaskInfo | None:
        """Commit a ``_resolve`` result, carrying the miss budget forward."""
        if info is None:
            self._cache[key] = _TaskEntry(
                info=None,
                miss_at=self._now(),
                miss_count=(prev.miss_count + 1) if prev is not None else 1,
            )
            return None
        self._cache[key] = _TaskEntry(info=info)
        return info

    def invalidate(self, task_id: str, session_name: str = "") -> None:
        """Drop a cached entry so the next lookup re-resolves.

        Still needed after t1322's identity keying: it is the only *immediate*
        retry for a cached negative (a backoff that is not yet due would
        otherwise return ``None`` again to a user's explicit gesture), and the
        only thing that re-decides ``_resolve``'s active-beats-archived
        precedence when both copies of a task exist.
        """
        self._cache.pop((session_name, task_id), None)


    def get_parent_id(self, task_id: str) -> str | None:
        """Extract parent task number from a child task ID."""
        if "_" not in task_id:
            return None
        return task_id.split("_", 1)[0]

    def blocking_dependencies(
        self,
        info: "TaskInfo",
        session_name: str = "",
        *,
        refresh: bool = True,
    ) -> list[str]:
        """Unsatisfied ``depends`` entries of an already-resolved task (t1310).

        Takes the resolved :class:`TaskInfo` rather than an id so the caller —
        which has just invalidated and re-read the target for display — reads
        each task file exactly once.

        A dependency counts as blocking unless it resolves with status
        ``Done``. An entry that does not resolve at all is reported as blocking
        too (fail-closed): a dangling id must be visible, never silently
        treated as satisfied. Archived dependencies resolve normally —
        :meth:`_resolve` searches ``aitasks/archived/`` — and carry
        ``status: Done``, so completed work does not show up as a blocker.

        **Freshness.** ``refresh=True`` invalidates each dependency before
        resolving it. Since t1322 the cache is identity-keyed, so a dependency
        flipping ``Ready`` → ``Done`` while a long-lived minimonitor is open is
        already picked up by ``get_task_info`` on its own — ``refresh=True`` is
        no longer what prevents a stale "still blocking" verdict. It is retained
        because it still does two things the identity gate cannot: it forces an
        immediate retry of a *negative* entry whose backoff is not yet due, and
        it re-decides ``_resolve``'s active-beats-archived precedence. This
        matches :meth:`find_ready_siblings`, which recomputes its
        ``blocking_ids`` by reading every sibling file from disk on each call.

        ``refresh=False`` therefore no longer serves stale content; it only
        skips the forced invalidation. Tests assert that distinction by counting
        ``_resolve`` calls over an *unchanged* file, not by rewriting one.
        """
        blocking: list[str] = []
        for dep in info.depends:
            if refresh:
                self.invalidate(dep, session_name)
            dep_info = self.get_task_info(dep, session_name)
            if dep_info is None or dep_info.status != "Done":
                blocking.append(dep)
        return blocking

    def find_next_sibling(
        self, task_id: str, session_name: str = ""
    ) -> tuple[str, str, str] | None:
        """Find the next Ready sibling/child task.

        If task_id is a child (e.g. "123_4"), returns the next Ready sibling
        under the same parent, excluding the current task. If task_id is a
        parent (e.g. "123"), returns the first Ready child of that parent.

        Returns ``(task_id, title, followup_kind)`` or None. ``followup_kind``
        is type-coerced to a string (``""`` when absent, or when frontmatter
        held a list / int / bool) but **not** validated against the vocabulary:
        an unrecognised value rides through verbatim so the render boundary
        (``followup_kinds.marker_for``) can show it as unrecognised rather than
        as "not a follow-up" (t1468_5).
        """
        if "_" in task_id:
            parent, _child = task_id.split("_", 1)
            exclude_id: str | None = task_id
        else:
            parent = task_id
            exclude_id = None

        root = self._root_for_session(session_name)
        search_dir = root / "aitasks" / f"t{parent}"
        if not search_dir.is_dir():
            return None

        candidates = []
        child_re = re.compile(rf'^t{re.escape(parent)}_(\d+)_')
        for path in sorted(search_dir.glob(f"t{parent}_*_*.md")):
            m = child_re.match(path.stem)
            if not m:
                continue
            sib_child = m.group(1)
            sib_id = f"{parent}_{sib_child}"
            if exclude_id is not None and sib_id == exclude_id:
                continue
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = parse_frontmatter(raw)
            if parsed is None:
                continue
            metadata, body, _ = parsed
            if str(metadata.get("status", "")).strip() != "Ready":
                continue
            title = None
            for line in body.splitlines():
                ls = line.strip()
                if ls.startswith("# "):
                    title = ls[2:].strip()
                    break
            if not title:
                parts = path.stem.split("_", 2)
                title = parts[2].replace("_", " ") if len(parts) > 2 else path.stem
            candidates.append((int(sib_child), sib_id, title,
                               normalize_followup_kind(
                                   metadata.get("followup_kind"))))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        _, sib_id, title, followup_kind = candidates[0]
        return (sib_id, title, followup_kind)

    def find_ready_siblings(
        self, task_id: str, session_name: str = ""
    ) -> list[tuple[str, str, list[str], str]]:
        """List pending Ready siblings of ``task_id``.

        Returns rows of ``(sib_id, title, blocking_sibling_ids, followup_kind)``
        sorted by child number ascending. ``blocking_sibling_ids`` lists sibling
        ids under the same parent that appear in this sibling's ``depends``
        field and are not yet ``Done`` — so callers can show a
        "blocked by tX" hint while still allowing the row to be picked.
        ``followup_kind`` carries auto-spawned-follow-up provenance under the
        same coercion rule as ``find_next_sibling`` (t1468_5).

        Same parent/exclude rules as ``find_next_sibling``: when ``task_id``
        is a child, the current sibling is excluded; when ``task_id`` is a
        parent, all Ready children are returned.
        """
        if "_" in task_id:
            parent, _child = task_id.split("_", 1)
            exclude_id: str | None = task_id
        else:
            parent = task_id
            exclude_id = None

        root = self._root_for_session(session_name)
        search_dir = root / "aitasks" / f"t{parent}"
        if not search_dir.is_dir():
            return []

        # First pass: collect every sibling's status + parsed metadata so
        # the second pass can compute "blocked by sibling" without re-reading.
        sib_status: dict[str, str] = {}
        parsed_rows: list[tuple[int, str, str, list[str], str]] = []
        child_re = re.compile(rf'^t{re.escape(parent)}_(\d+)_')
        for path in sorted(search_dir.glob(f"t{parent}_*_*.md")):
            m = child_re.match(path.stem)
            if not m:
                continue
            sib_child = m.group(1)
            sib_id = f"{parent}_{sib_child}"
            try:
                raw = path.read_text(encoding="utf-8")
            except OSError:
                continue
            parsed = parse_frontmatter(raw)
            if parsed is None:
                continue
            metadata, body, _ = parsed
            status = str(metadata.get("status", "")).strip()
            sib_status[sib_id] = status
            if status != "Ready":
                continue
            if exclude_id is not None and sib_id == exclude_id:
                continue
            title = None
            for line in body.splitlines():
                ls = line.strip()
                if ls.startswith("# "):
                    title = ls[2:].strip()
                    break
            if not title:
                parts = path.stem.split("_", 2)
                title = parts[2].replace("_", " ") if len(parts) > 2 else path.stem
            depends_raw = metadata.get("depends", []) or []
            # Normalize "t42" / "42" / 42 to bare numeric strings.
            depends_norm = [str(d).lstrip("t") for d in depends_raw]
            parsed_rows.append((
                int(sib_child), sib_id, title, depends_norm,
                normalize_followup_kind(metadata.get("followup_kind")),
            ))

        if not parsed_rows:
            return []

        # Second pass: a blocker is a depends entry whose normalized form
        # matches "<parent>_<n>" of another sibling whose status is not Done.
        rows: list[tuple[str, str, list[str], str]] = []
        for (_child_num, sib_id, title, depends_norm,
                followup_kind) in sorted(parsed_rows, key=lambda r: r[0]):
            blocking: list[str] = []
            for dep in depends_norm:
                # Only sibling deps shaped as "<parent>_<n>" are relevant
                # here; cross-parent deps are not surfaced (the "blocked by
                # sibling" hint is intentionally scoped to siblings).
                if not dep.startswith(f"{parent}_"):
                    continue
                if sib_status.get(dep, "") != "Done":
                    blocking.append(dep)
            rows.append((sib_id, title, blocking, followup_kind))
        return rows

    def _resolve(self, task_id: str, session_name: str = "") -> TaskInfo | None:
        """Look up task file and parse its content. Pure Python, no subprocess.

        Searches both the active location (``aitasks/``) and the archived
        location (``aitasks/archived/``) so that monitor TUIs can keep
        showing task info for an agent pane whose task has already been
        archived. Active dirs win when the same id is present in both.
        Tasks bundled into ``aitasks/archived/_b0/old<N>.tar.zst`` are not
        extracted — those agents are old enough that lookup misses are
        acceptable.
        """
        root = self._root_for_session(session_name)
        tasks_dir = root / "aitasks"
        plans_dir = root / "aiplans"
        archived_tasks_dir = tasks_dir / "archived"
        archived_plans_dir = plans_dir / "archived"

        if "_" in task_id:
            parent, child = task_id.split("_", 1)
            pattern = f"t{parent}_{child}_*.md"
            search_dirs = (
                tasks_dir / f"t{parent}",
                archived_tasks_dir / f"t{parent}",
            )
        else:
            pattern = f"t{task_id}_*.md"
            search_dirs = (tasks_dir, archived_tasks_dir)

        task_path = None
        for d in search_dirs:
            if not d.is_dir():
                continue
            matches = list(d.glob(pattern))
            if matches:
                task_path = matches[0]
                break
        if task_path is None:
            return None

        # Sample the file identity BEFORE the read, never after (t1322).
        # aitask_archive.sh rewrites the task file by rename (`sed -i`,
        # `awk > tmp && mv`), so a read that races a rewrite returns the OLD
        # inode's bytes; an identity sampled afterwards would belong to the NEW
        # file and would pin that stale content in the cache permanently.
        identity = _file_identity(str(task_path))

        try:
            raw = task_path.read_text(encoding="utf-8")
        except OSError:
            return None

        parsed = parse_frontmatter(raw)
        if parsed is None:
            return None
        metadata, body, _ = parsed

        # Extract title: first markdown heading or derive from filename
        title = None
        for line in body.splitlines():
            line_s = line.strip()
            if line_s.startswith("# "):
                title = line_s[2:].strip()
                break
        if not title:
            stem = task_path.stem
            parts = stem.split("_", 1)
            title = parts[1].replace("_", " ") if len(parts) > 1 else stem

        # Find plan file (active dir first, archived as fallback).
        plan_content = None
        if "_" in task_id:
            parent, child = task_id.split("_", 1)
            plan_pattern = f"p{parent}_{child}_*.md"
            plan_dirs = (
                plans_dir / f"p{parent}",
                archived_plans_dir / f"p{parent}",
            )
        else:
            plan_pattern = f"p{task_id}_*.md"
            plan_dirs = (plans_dir, archived_plans_dir)

        for pd in plan_dirs:
            if not pd.is_dir():
                continue
            plan_matches = list(pd.glob(plan_pattern))
            if not plan_matches:
                continue
            try:
                plan_raw = plan_matches[0].read_text(encoding="utf-8")
                if plan_raw.startswith("---"):
                    fm_parts = plan_raw.split("---", 2)
                    if len(fm_parts) >= 3:
                        plan_content = fm_parts[2].strip()
                    else:
                        plan_content = plan_raw
                else:
                    plan_content = plan_raw
            except OSError:
                pass
            break

        return TaskInfo(
            task_id=task_id,
            task_file=str(task_path.relative_to(root)),
            title=title,
            priority=str(metadata.get("priority", "")),
            effort=str(metadata.get("effort", "")),
            issue_type=str(metadata.get("issue_type", "")),
            status=str(metadata.get("status", "")),
            body=body,
            plan_content=plan_content,
            task_file_abs=str(task_path),
            # Same normalization as find_ready_siblings: "t42" / "42" / 42 all
            # become the bare "42".
            depends=[
                str(d).lstrip("t") for d in (metadata.get("depends", []) or [])
            ],
            file_identity=identity,
        )
