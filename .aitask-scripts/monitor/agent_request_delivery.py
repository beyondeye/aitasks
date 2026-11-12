"""agent_request_delivery.py - type a request into an agent pane, guarded (t2211_4).

The sitrep TUI's agentic keys type a one-line request (``>t c12``) into the
sitrep agent's composer and submit it. A live, unfrozen pane is NOT proof that
typing is safe: at a dialog Enter answers it, a user's unsent draft would be
submitted mixed with ours, a working agent garbles input, and in tmux
copy-mode Enter is copy-pipe-and-cancel. Delivery is therefore three separately
observed phases, each failing closed:

1. **Readiness** (positive detection, never retried): two raw tails
   ``COMPOSER_DRAIN_SECONDS`` apart must both read ``SHADOW_READY`` (an EMPTY
   composer) and be byte-identical, and the pane must not be in a mode. Only
   ``review_loop.shadow_state`` decides -- there is no second detector.
2. **Dispatch with an observable result**: ``monitor_core.guarded_paste_text``
   -- the text through stdin into a named buffer, pasted by ONE ``if-shell``
   whose condition is the run identity + "not in a mode", acked by a nonce.
3. **Submission**, separate from dispatch: before EVERY Enter (retries
   included) the current composer's complete payload must equal the request
   (``review_loop.composer_payload`` + :func:`payload_matches`), and the pane
   mode is the last thing read; the Enter is itself a guarded, acked dispatch.
   A re-capture then decides whether it went.

Every outcome is one :class:`DeliveryResult` code; ``unknown`` is never
reported as sent. Nothing here is cached across calls: the agent pane and its
run identity are re-resolved on every request.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import unicodedata
from dataclasses import dataclass

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import agent_keys  # noqa: E402
from monitor import monitor_core  # noqa: E402
from monitor import review_loop  # noqa: E402  (the one readiness / payload reader)
from tmux_exec import tmux_os_path  # noqa: E402

# -- result vocabulary ----------------------------------------------------------

SUBMITTED = "submitted"
TYPED = "typed_not_submitted"
TYPED_IN_MODE = "typed_not_submitted:in_mode"
TYPED_MODE_UNREADABLE = "typed_not_submitted:mode_unreadable"
SKIPPED = "skipped"
UNKNOWN = "unknown"
REFUSED = "refused"

#: ``refused:<reason>`` -- nothing was typed into the agent.
NOT_READY_DIALOG = "not_ready:dialog"
NOT_READY_DRAFT = "not_ready:draft"
NOT_READY_WORKING = "not_ready:working"
NOT_READY_UNKNOWN = "not_ready:unknown"
NOT_READY_IN_MODE = "not_ready:in_mode"
NOT_READY_MODE_UNREADABLE = "not_ready:mode_unreadable"
READY = "ready"
R_IDENTITY_CHANGED = "identity_changed"
R_NO_AGENT = "no_agent"
R_FROZEN = "frozen"
R_DISPATCH_FAILED = "dispatch_failed"
R_INVALID_REQUEST = "invalid_request"

#: Longest request line typed into an agent (a template plus the user's text).
REQUEST_MAX_CHARS = 400

_MESSAGES = {
    SUBMITTED: "Sent to the sitrep agent",
    TYPED: "Typed into the sitrep agent but NOT submitted — check its composer",
    TYPED_IN_MODE: ("Typed into the sitrep agent but NOT submitted: its pane is in a tmux "
                    "mode (e.g. scrolled back). The request is waiting in its composer — "
                    "leave the mode and press Enter there"),
    TYPED_MODE_UNREADABLE: ("Typed into the sitrep agent but NOT submitted: its pane mode "
                            "could not be read. The request is waiting in its composer"),
    SKIPPED: "Not sent: the sitrep agent pane changed just before typing (nothing typed)",
    UNKNOWN: "Could not verify what happened — look at the sitrep agent pane",
}
_REFUSALS = {
    NOT_READY_DIALOG: "the agent is waiting for an answer to a dialog",
    NOT_READY_DRAFT: "the agent's composer holds unsent text (left untouched)",
    NOT_READY_WORKING: "the agent is working",
    NOT_READY_UNKNOWN: "the agent's state could not be read",
    NOT_READY_IN_MODE: "the agent pane is in a tmux mode (e.g. scrolled back)",
    NOT_READY_MODE_UNREADABLE: "the agent pane's mode could not be read",
    R_IDENTITY_CHANGED: "the agent was replaced before the Enter",
    R_NO_AGENT: "no running sitrep agent pane for this repository",
    R_FROZEN: "the sitrep agent is frozen",
    R_DISPATCH_FAILED: "the request could not be handed to tmux (nothing typed)",
    R_INVALID_REQUEST: "the request is not a single plain line",
}


@dataclass(frozen=True)
class DeliveryResult:
    """One delivery's outcome: ``code`` is the result vocabulary above,
    ``detail`` a short machine-readable reason, ``request`` the line typed."""

    code: str
    detail: str = ""
    request: str = ""

    @property
    def submitted(self) -> bool:
        return self.code == SUBMITTED

    def message(self) -> str:
        """The user-facing sentence (plain text; render it markup-free)."""
        if self.code.startswith(REFUSED + ":"):
            reason = self.code[len(REFUSED) + 1:]
            return f"Not sent: {_REFUSALS.get(reason, reason)}"
        return _MESSAGES.get(self.code, self.code)


def _refused(reason: str, detail: str = "", request: str = "") -> DeliveryResult:
    return DeliveryResult(f"{REFUSED}:{reason}", detail, request)


# -- the request line --------------------------------------------------------------

#: First characters that switch an agent's composer into another mode (a slash
#: command, a shell escape, a memory note, a mention) instead of a message.
_SPECIAL_PREFIX = "/!#@$&"


def request_line_error(text: str, *, check_prefix: bool = True) -> str:
    """Why ``text`` cannot be typed as one request line, or ``""``.

    One line of printable characters, single-spaced, no leading/trailing
    space (the composer proof matches it exactly, and a display wrap consumes
    exactly one space), not starting with a mode character, and no ``@`` in
    its LAST token: with the cursor right after a ``@token`` every measured
    agent opens a file-suggestion list that takes the Enter (t2211_4 spike).

    ``check_prefix=False`` validates a FRAGMENT that will follow a fixed
    request prefix (the ask dialog's question): a mode character only matters
    as the first character of the whole line, so the assembled request is
    checked with the prefix rule, never the fragment.
    """
    if not text:
        return "empty"
    if len(text) > REQUEST_MAX_CHARS:
        return "too_long"
    for ch in text:
        cat = unicodedata.category(ch)
        if cat in ("Cc", "Cf", "Zl", "Zp", "Co", "Cs", "Cn") or (cat == "Zs" and ch != " "):
            return "control_character"
    if text != text.strip(" ") or "  " in text:
        return "spacing"
    if check_prefix and text[0] in _SPECIAL_PREFIX:
        return "special_prefix"
    if "@" in text.rsplit(" ", 1)[-1]:
        return "trailing_mention"
    return ""


def display_width(text: str) -> int:
    """Terminal columns ``text`` occupies (East-Asian wide/full = 2, combining = 0)."""
    width = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return width


_WORD_RE = re.compile(r"\S+")
#: The smallest piece a hyphen-breaking agent could have kept on the row: up to
#: and including the first hyphen, else up to the next space (t2280). Smaller
#: is the conservative reading: it makes a break harder, never easier, to justify.
_FRAGMENT_RE = re.compile(r"[^\s-]*-|[^\s-]+")


def _moved_piece(payload: "review_loop.ComposerPayload", expected: str, pos: int):
    """The piece a break before ``pos`` moved to the next row, and its fit limit.

    The limit depends on how the piece ends. Followed by a space: ``wrap_width``
    (measured by the word-wrap edges, and for opencode by its ``re-`` / ``run``
    break). Ending in a hyphen: ``content_width`` (measured: codex and opencode
    keep a hyphen-ended piece on the row up to the content width). Ending the
    text: unmeasured, so ``content_width``, the sound upper bound -- no row holds
    more -- under which an unmeasured ending can only fail closed.
    """
    m = (_FRAGMENT_RE if payload.hyphen_breaks else _WORD_RE).match(expected, pos)
    if not m or not m.group(0):
        return "", 0
    end = m.end()
    limit = payload.wrap_width if expected[end:end + 1] == " " else payload.content_width
    return m.group(0), limit


def _hyphen_justified(payload, row: str, expected: str, pos: int) -> bool:
    """Would the piece at ``pos`` not have fit after ``row`` (which ends in ``-``)?"""
    piece, limit = _moved_piece(payload, expected, pos)
    return bool(piece) and display_width(row) + display_width(piece) > limit


def payload_matches(payload: "review_loop.ComposerPayload | None", expected: str) -> bool:
    """True iff the composer's displayed payload is EXACTLY ``expected``.

    Every display row must be the next slice of ``expected``; a row break is
    allowed only where it is a justified display wrap: a word wrap (one space
    of ``expected`` sits there, consumed, and the moved piece would not have
    fit: ``row + 1 + piece > limit``), a hyphen break (only for an agent with
    ``hyphen_breaks``: the row ends in ``-``, nothing is consumed, and ``row +
    piece > limit``) or a hard break inside a token (no space there, and the
    row fills ``content_width``; a hyphen break that is not justified is still
    accepted as this). Text left over on either side, an extra row or an
    unjustified break -> False. A break that is not justified is a typed
    newline, so the composer is not ``expected``.

    The moved piece and its ``limit`` come from :func:`_moved_piece`: for a
    hyphen-breaking agent the piece is the smallest one it could have kept on
    the row (up to the first hyphen), and the limit follows the piece's ending
    -- ``wrap_width`` before a space, else ``content_width``. Measured at 60,
    44 and 120 columns (t2211_4, t2280); an unmeasured ending (the end of the
    text) gets the sound upper bound, so it can only fail closed.
    """
    if payload is None or not payload.lines or not expected:
        return False
    pos = 0
    last = len(payload.lines) - 1
    for idx, row in enumerate(payload.lines):
        if not row or not expected.startswith(row, pos):
            return False
        pos += len(row)
        if idx == last:
            break
        if expected[pos:pos + 1] == " ":
            pos += 1
            piece, limit = _moved_piece(payload, expected, pos)
            if not piece or display_width(row) + 1 + display_width(piece) <= limit:
                return False
        elif payload.hyphen_breaks and row.endswith("-") and _hyphen_justified(
                payload, row, expected, pos):
            pass
        elif display_width(row) != payload.content_width:
            return False
    return pos == len(expected)


# -- phase 1: readiness ----------------------------------------------------------------

def readiness_verdict(tail1: "str | None", tail2: "str | None", agent: str,
                      in_mode: "bool | None") -> str:
    """``ready`` or a ``not_ready:<reason>`` from two raw tails and the mode.

    Only :func:`review_loop.shadow_state` classifies. Precedence follows its
    verdict order (a dialog first; ``working`` only outranks a would-be ready):
    an agent without a detector, a failed capture or ``unknown`` -> unknown;
    a dialog on either tail -> dialog; typed text -> draft; working, or two
    tails that differ -> working; then the mode (None = unreadable).
    """
    key = (agent or "").strip().lower()
    if key not in review_loop.SHADOW_STATE_DETECTORS or tail1 is None or tail2 is None:
        return NOT_READY_UNKNOWN
    states = (review_loop.shadow_state(tail1, key), review_loop.shadow_state(tail2, key))
    if review_loop.SHADOW_DIALOG in states:
        return NOT_READY_DIALOG
    if review_loop.SHADOW_BUSY in states:
        return NOT_READY_DRAFT
    if review_loop.SHADOW_UNKNOWN in states:
        return NOT_READY_UNKNOWN
    if review_loop.SHADOW_WORKING in states or tail1 != tail2:
        return NOT_READY_WORKING
    if in_mode is None:
        return NOT_READY_MODE_UNREADABLE
    if in_mode:
        return NOT_READY_IN_MODE
    return READY


# -- the target --------------------------------------------------------------------------

#: One read of the target: the run identity, then the sitrep stamp, deadness
#: and the pane's command (for the agent key).
TARGET_FORMAT = (monitor_core.RUN_IDENTITY_FORMAT
                 + f"\t#{{{monitor_core.SITREP_ROOT_OPTION}}}\t#{{pane_dead}}"
                 "\t#{pane_current_command}")


@dataclass(frozen=True)
class Target:
    identity: "monitor_core.RunIdentity | None"
    refusal: str = ""
    command: str = ""


def parse_target(rc: int, out: str, pane_id: str, root: str) -> Target:
    """The agent run behind ``pane_id``, or why it is not a target.

    Only a live, unfrozen pane STAMPED ``@aitask_sitrep_root`` = ``root`` is
    one: the roles lookup's name+cwd fallback, a pane carrying the TUI
    marker, a dead or vanished pane are ``no_agent``; a frozen stand-in is
    ``frozen``.
    """
    fields = (out.splitlines() or [""])[0].split("\t") if rc == 0 else []
    if len(fields) < 8:
        return Target(None, R_NO_AGENT)
    ident = monitor_core.parse_run_identity(0, "\t".join(fields[:5]), pane_id)
    if ident is None:
        return Target(None, R_NO_AGENT)
    stamp, dead = fields[5].strip(), fields[6].strip()
    command = "\t".join(fields[7:]).strip()
    if ident.frozen_record:
        return Target(ident, R_FROZEN, command)
    if ident.sitrep_tui_root or dead == "1" or not stamp or tmux_os_path(stamp) != root:
        return Target(ident, R_NO_AGENT, command)
    return Target(ident, "", command)


def agent_key_for(target: Target) -> str:
    """The agent key of the target pane (``agent_keys.agent_key_from_pane``:
    the command, the pane process's comm, one level of children)."""
    ident = target.identity
    if ident is None:
        return ""
    return agent_keys.agent_key_from_pane(target.command, int(ident.pane_pid),
                                          ident.pane_id)


async def _pane_width(monitor, pane_id: str) -> "int | None":
    rc, out = await monitor.tmux_run_async(
        ["display-message", "-p", "-t", pane_id, "#{pane_id}\t#{pane_width}"], timeout=3.0)
    if rc != 0:
        return None
    found, _, width = (out.splitlines() or [""])[0].partition("\t")
    width = width.strip()
    return int(width) if found.strip() == pane_id and width.isdigit() else None


async def _pause(pause, phase: str) -> None:
    if pause is not None:
        await pause(phase)


# -- the delivery --------------------------------------------------------------------------

async def deliver_sitrep_request(monitor, root: str, text: str, *, roles=None,
                                 resolve_agent=None, pause=None, sleep=asyncio.sleep,
                                 nonce=None) -> DeliveryResult:
    """Type ``text`` into the sitrep agent of ``root`` and submit it, guarded.

    ``monitor`` is duck-typed: ``tmux_run``, ``tmux_run_async``,
    ``tmux_run_input``. Seams for tests: ``roles(monitor, root)`` (default
    ``monitor_core.find_sitrep_roles``), ``resolve_agent(target)`` (default
    :func:`agent_key_for`), ``pause(phase)`` awaited at ``after_readiness``,
    ``after_paste`` and ``before_retry``, ``sleep`` and ``nonce()``.
    """
    roles = roles or monitor_core.find_sitrep_roles
    resolve_agent = resolve_agent or agent_key_for
    nonce = nonce or monitor_core.new_dispatch_nonce
    bad = request_line_error(text)
    if bad:
        return _refused(R_INVALID_REQUEST, bad, text)

    try:
        ok, agent_pane, _tui = await asyncio.to_thread(roles, monitor, root)
    except Exception:  # noqa: BLE001 - an unanswered query is never "no agent"
        ok, agent_pane = False, None
    if not ok:
        return _refused(R_NO_AGENT, "roles_query_failed", text)
    if not agent_pane:
        return _refused(R_NO_AGENT, "", text)
    rc, out = await asyncio.to_thread(
        monitor.tmux_run, ["display-message", "-p", "-t", agent_pane, TARGET_FORMAT])
    target = parse_target(rc, out, agent_pane, root)
    if target.refusal:
        return _refused(target.refusal, "", text)
    ident = target.identity
    pane = ident.pane_id
    try:
        agent = await asyncio.to_thread(resolve_agent, target)
    except Exception:  # noqa: BLE001
        agent = ""
    if (agent not in review_loop.SHADOW_STATE_DETECTORS
            or agent not in review_loop.PAYLOAD_GRAMMAR_AGENTS):
        return _refused(NOT_READY_UNKNOWN, f"agent:{agent or 'unresolved'}", text)

    # Phase 1 -- readiness.
    tail1 = await monitor_core.capture_raw_tail(monitor, pane)
    await sleep(review_loop.COMPOSER_DRAIN_SECONDS)
    tail2 = await monitor_core.capture_raw_tail(monitor, pane)
    in_mode, _mode = await monitor_core.query_pane_mode(monitor, pane)
    verdict = readiness_verdict(tail1, tail2, agent, in_mode)
    if verdict != READY:
        return _refused(verdict, "", text)

    # Phase 2 -- dispatch.
    await _pause(pause, "after_readiness")
    state, reason = await asyncio.to_thread(
        monitor_core.guarded_paste_text, monitor, ident, text, nonce())
    if state == monitor_core.DISPATCH_FAILED:
        return _refused(R_DISPATCH_FAILED, reason, text)
    if state == monitor_core.DISPATCH_SKIPPED:
        return DeliveryResult(SKIPPED, reason, text)
    if state != monitor_core.DISPATCH_SENT:
        return DeliveryResult(UNKNOWN, "paste_unacknowledged", text)

    # Phase 3 -- submission.
    await _pause(pause, "after_paste")
    for attempt in range(review_loop.SHADOW_SUBMIT_RETRIES + 1):
        if attempt:
            await _pause(pause, "before_retry")
        await sleep(review_loop.COMPOSER_DRAIN_SECONDS)
        tail = await monitor_core.capture_raw_tail(monitor, pane)
        width = await _pane_width(monitor, pane)
        before = review_loop.shadow_state(tail, agent)
        if before != review_loop.SHADOW_BUSY:
            detail = {review_loop.SHADOW_DIALOG: "pre_enter_dialog",
                      review_loop.SHADOW_UNKNOWN: "pre_enter_unreadable"}.get(
                          before, "text_not_in_composer")
            return DeliveryResult(UNKNOWN, detail, text)
        payload = review_loop.composer_payload(tail, agent, width)
        if payload is None:
            return DeliveryResult(UNKNOWN, "composer_unprovable", text)
        if not payload_matches(payload, text):
            if attempt == 0:
                return DeliveryResult(TYPED, "composer_changed", text)
            return DeliveryResult(UNKNOWN, "composer_changed_after_enter", text)
        # The pane mode is the LAST read before every Enter (t2001); the Enter's
        # own condition re-checks it in the server.
        in_mode, _mode = await monitor_core.query_pane_mode(monitor, pane)
        if in_mode is None:
            return DeliveryResult(TYPED_MODE_UNREADABLE, "", text)
        if in_mode:
            return DeliveryResult(TYPED_IN_MODE, "", text)
        state, reason = await asyncio.to_thread(
            monitor_core.guarded_send_key, monitor, ident, "Enter", nonce())
        if state == monitor_core.DISPATCH_SKIPPED:
            if reason == monitor_core.SKIP_IN_MODE:
                return DeliveryResult(TYPED_IN_MODE, "enter_skipped", text)
            return _refused(R_IDENTITY_CHANGED, "enter_skipped", text)
        if state != monitor_core.DISPATCH_SENT:
            return DeliveryResult(UNKNOWN, "enter_unacknowledged", text)
        await sleep(review_loop.COMPOSER_DRAIN_SECONDS)
        after = await monitor_core.capture_raw_tail(monitor, pane)
        after_state = review_loop.shadow_state(after, agent)
        if after_state in (review_loop.SHADOW_READY, review_loop.SHADOW_WORKING):
            return DeliveryResult(SUBMITTED, "", text)
        if after_state != review_loop.SHADOW_BUSY:
            return DeliveryResult(UNKNOWN, f"post_enter_{after_state}", text)
        # Still BUSY: the Enter was swallowed, or the request went and someone
        # typed again. Only a composer that still holds exactly the request is
        # a swallowed Enter; anything else means our text may have been
        # submitted, and "not submitted" would invite a duplicate.
        held = review_loop.composer_payload(
            after, agent, await _pane_width(monitor, pane))
        if held is None:
            return DeliveryResult(UNKNOWN, "composer_unprovable_after_enter", text)
        if not payload_matches(held, text):
            return DeliveryResult(UNKNOWN, "composer_changed_after_enter", text)
    return DeliveryResult(TYPED, "submit_unconfirmed", text)
