"""agent_submit.py - submit text already typed into an agent's composer (t2275).

Two callers type a line into a coding agent's composer and must then press
Enter only when that is provably safe: the minimonitor's auto-recheck (the
recheck prompt into the SHADOW pane, ``minimonitor_app._submit_shadow_prompt``)
and the sitrep TUI's request delivery (``agent_request_delivery
.deliver_sitrep_request``, phase 3). They used to carry two copies of the same
loop, and the copies drifted: the sitrep one proved the composer's payload
before each Enter and the minimonitor one did not (t2274). This module is the
ONE implementation of that loop. It owns mechanics only and returns a neutral
:class:`SubmitOutcome`; each caller maps it onto its own result vocabulary.

**The sequence, per attempt** (``review_loop.SHADOW_SUBMIT_RETRIES + 1`` of them):

1. ``before_retry()`` on every attempt after the first;
2. the drain (``review_loop.COMPOSER_DRAIN_SECONDS``), then the capture, the
   pane width and the pane mode, **in that order: the mode is the last read
   before every Enter** (t2001 -- in a tmux mode ``send-keys`` goes to the
   mode's key table, and no capture can see a mode);
3. ``checkpoint("pre_enter", obs)``, a SYNCHRONOUS callable, so no await can
   separate it from the verdict and the Enter. A non-None return stops the
   loop (``STOPPED``) ahead of every verdict: the minimonitor's delivery-token
   check (supersession always wins);
4. the pre-Enter proof, which authorises an ACTION and so fails CLOSED: the
   composer reads ``SHADOW_BUSY`` **and** its complete displayed payload
   (``review_loop.composer_payload``) is exactly ``text``
   (:func:`payload_matches`), and the pane is not in a mode. ``SHADOW_BUSY``
   alone only says the composer holds SOME text -- the user's words appended
   to ours, or a draft typed after a real submit, would be submitted;
5. ``send_enter()``, the caller's transport, returning a ``monitor_core``
   dispatch ``(state, reason)``. Both callers use the guarded, acked
   ``monitor_core.guarded_send_key`` bound to the run identity they read before
   typing (the minimonitor since t2309), so tmux re-checks "same run, not in a
   mode" atomically with the keystroke; any result but ``sent`` is
   ``ENTER_NOT_SENT`` with that ``(state, reason)`` on ``SubmitOutcome.enter``;
6. the post-Enter read, which only decides what to CLAIM about a key already
   sent: READY / WORKING is a submit; any other non-BUSY verdict is
   unverified; BUSY is a swallowed Enter -- retried -- ONLY when the composer
   still holds exactly ``text``. Any other BUSY composer means our text may
   already have gone and someone typed again: never retried (a retry would
   submit the user's draft).

After the last attempt ``checkpoint("exhausted", obs)`` runs once more, then
``EXHAUSTED``.

**Lookup sites.** Every collaborator is resolved by module attribute at call
time -- ``monitor_core.capture_raw_tail`` / ``query_pane_mode``,
``review_loop.shadow_state`` / ``composer_payload`` and this module's own
:func:`payload_matches` -- never through a ``from ... import``, so a test (or a
mutant in ``tests/test_sitrep_request_delivery_live.sh``) that patches one of
them reaches the real decision.

**The composer matcher** (:func:`payload_matches` and its helpers) lives here
because both callers need it and the minimonitor must not import the sitrep
module; ``agent_request_delivery`` re-exports it unchanged.
"""

from __future__ import annotations

import inspect
import os
import re
import sys
import unicodedata
from dataclasses import dataclass

_SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_SCRIPTS, os.path.join(_SCRIPTS, "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from monitor import monitor_core  # noqa: E402
from monitor import review_loop  # noqa: E402

# -- the composer matcher -----------------------------------------------------------


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


async def pane_width(monitor, pane_id: str) -> "int | None":
    """``#{pane_width}`` of ``pane_id``, or None (failed, or not that pane)."""
    rc, out = await monitor.tmux_run_async(
        ["display-message", "-p", "-t", pane_id, "#{pane_id}\t#{pane_width}"], timeout=3.0)
    if rc != 0:
        return None
    found, _, width = (out.splitlines() or [""])[0].partition("\t")
    width = width.strip()
    return int(width) if found.strip() == pane_id and width.isdigit() else None


# -- the submit loop ------------------------------------------------------------------

#: Neutral outcome kinds. They name what was OBSERVED; each caller decides what
#: that means in its own vocabulary (and which of them are holds or failures).
PRE_NOT_BUSY = "pre_not_busy"                 # state = the verdict; no Enter
PRE_UNPROVABLE = "pre_unprovable"             # BUSY, payload not provable; no Enter
PRE_CHANGED = "pre_changed"                   # BUSY, payload is not the text; no Enter
PRE_MODE_UNREADABLE = "pre_mode_unreadable"   # proven, mode unreadable; no Enter
PRE_IN_MODE = "pre_in_mode"                   # proven, pane in a mode; no Enter
ENTER_NOT_SENT = "enter_not_sent"             # the transport did not send it
POST_SUBMITTED = "post_submitted"             # READY / WORKING after the Enter
POST_UNVERIFIED = "post_unverified"           # state = a non-BUSY, non-submit verdict
POST_UNPROVABLE = "post_unprovable"           # BUSY after the Enter, not provable
POST_CHANGED = "post_changed"                 # BUSY after the Enter, other text
EXHAUSTED = "exhausted"                       # every Enter was swallowed
STOPPED = "stopped"                           # the checkpoint stopped the loop

OUTCOME_KINDS = (PRE_NOT_BUSY, PRE_UNPROVABLE, PRE_CHANGED, PRE_MODE_UNREADABLE,
                 PRE_IN_MODE, ENTER_NOT_SENT, POST_SUBMITTED, POST_UNVERIFIED,
                 POST_UNPROVABLE, POST_CHANGED, EXHAUSTED, STOPPED)


@dataclass(frozen=True)
class Observation:
    """What one attempt's pre-Enter reads saw (``state``: a ``SHADOW_*``)."""

    attempt: int
    state: str
    in_mode: "bool | None"
    mode_name: str


@dataclass(frozen=True)
class SubmitOutcome:
    """The loop's result. ``state``: the ``SHADOW_*`` verdict of the read that
    decided it; ``obs``: the last pre-Enter observation; ``enter``: the
    transport's ``(state, reason)`` for ``ENTER_NOT_SENT``; ``stop``: the
    checkpoint's return value for ``STOPPED``."""

    kind: str
    attempt: int
    state: str = ""
    obs: "Observation | None" = None
    enter: tuple = ("", "")
    stop: object = None


async def submit_typed_text(monitor, pane: str, agent: str, text: str, *,
                            send_enter, sleep, checkpoint=None,
                            before_retry=None) -> SubmitOutcome:
    """Press Enter on ``text`` already typed into ``pane``'s composer, guarded.

    ``send_enter``: a zero-argument ``async def`` returning the
    ``monitor_core`` dispatch ``(state, reason)``, awaited exactly once per
    Enter. It must be a coroutine function: a plain callable would send the key
    and only then fail at the ``await``, skipping the post-Enter verification,
    so one is refused before the pane is touched. ``sleep(seconds)``: the
    drain. ``checkpoint(where, obs)``: synchronous, ``where`` is
    ``"pre_enter"`` or ``"exhausted"``; non-None stops the loop.
    ``before_retry()``: awaited before every attempt after the first.
    """
    if not inspect.iscoroutinefunction(send_enter):
        raise TypeError("send_enter must be an async def (a coroutine function)")
    obs = None
    for attempt in range(review_loop.SHADOW_SUBMIT_RETRIES + 1):
        if attempt and before_retry is not None:
            await before_retry()
        await sleep(review_loop.COMPOSER_DRAIN_SECONDS)
        tail = await monitor_core.capture_raw_tail(monitor, pane)
        width = await pane_width(monitor, pane)
        # The mode is the LAST read before every Enter (t2001).
        in_mode, mode_name = await monitor_core.query_pane_mode(monitor, pane)
        state = review_loop.shadow_state(tail, agent)
        obs = Observation(attempt, state, in_mode, mode_name)
        if checkpoint is not None:
            stop = checkpoint("pre_enter", obs)
            if stop is not None:
                return SubmitOutcome(STOPPED, attempt, state, obs, stop=stop)
        if state != review_loop.SHADOW_BUSY:
            return SubmitOutcome(PRE_NOT_BUSY, attempt, state, obs)
        payload = review_loop.composer_payload(tail, agent, width)
        if payload is None:
            return SubmitOutcome(PRE_UNPROVABLE, attempt, state, obs)
        if not payload_matches(payload, text):
            return SubmitOutcome(PRE_CHANGED, attempt, state, obs)
        if in_mode is None:
            return SubmitOutcome(PRE_MODE_UNREADABLE, attempt, state, obs)
        if in_mode:
            return SubmitOutcome(PRE_IN_MODE, attempt, state, obs)
        enter = tuple(await send_enter())
        if enter[0] != monitor_core.DISPATCH_SENT:
            return SubmitOutcome(ENTER_NOT_SENT, attempt, state, obs, enter=enter)
        await sleep(review_loop.COMPOSER_DRAIN_SECONDS)
        after = await monitor_core.capture_raw_tail(monitor, pane)
        after_state = review_loop.shadow_state(after, agent)
        if after_state in (review_loop.SHADOW_READY, review_loop.SHADOW_WORKING):
            return SubmitOutcome(POST_SUBMITTED, attempt, after_state, obs)
        if after_state != review_loop.SHADOW_BUSY:
            return SubmitOutcome(POST_UNVERIFIED, attempt, after_state, obs)
        # Still BUSY: the Enter was swallowed, or the text went and someone
        # typed again. Only a composer that still holds exactly the text is a
        # swallowed Enter; anything else means ours may have been submitted,
        # and a retry would submit the other text.
        held = review_loop.composer_payload(after, agent, await pane_width(monitor, pane))
        if held is None:
            return SubmitOutcome(POST_UNPROVABLE, attempt, after_state, obs)
        if not payload_matches(held, text):
            return SubmitOutcome(POST_CHANGED, attempt, after_state, obs)
    attempts = review_loop.SHADOW_SUBMIT_RETRIES
    if checkpoint is not None:
        stop = checkpoint("exhausted", obs)
        if stop is not None:
            return SubmitOutcome(STOPPED, attempts, review_loop.SHADOW_BUSY, obs, stop=stop)
    return SubmitOutcome(EXHAUSTED, attempts, review_loop.SHADOW_BUSY, obs)
