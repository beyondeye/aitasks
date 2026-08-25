"""Pure decision core for the minimonitor shadow auto-recheck loop (t1159_2).

When armed (minimonitor's ``L``), the loop injects a single-line "refetch and
recheck round N" into the SHADOW pane after the followed agent settles at a
prompt with output the shadow has not yet read. This module owns every
decision; it performs no I/O (no tmux, no Textual, no subprocess) so the whole
state machine is unit-testable like ``concern_parser``.

Contract highlights (the full safety contract lives in
``aidocs/framework/shadow_agent.md`` → "Review-loop automation"):

- **Edge-driven.** A fired recheck makes the shadow re-read the followed pane,
  which re-stamps ``@aitask_shadow_analyzed_at`` and thereby CLEARS the very
  staleness that triggered the fire (structurally: only a shadow pane reading
  its own bound agent stamps — ``aitask_shadow_capture.sh``). After a fire the
  controller stays FIRED until it positively observes ``stale is False``, then
  re-arms. Level-driven logic would fire forever or never.
- **Tri-state discipline.** ``stale``, ``shadow_ready``, ``agent_present`` and
  ``shadow_present`` all admit ``None`` = "cannot tell"; ``None`` never
  advances, never clears, never disarms. Disarm requires positively verified
  absence (``False``), so a transient tmux failure cannot destroy an armed
  loop.
- **Delivery is serialized.** A granted fire enters DELIVERING synchronously
  inside :meth:`ReviewLoopController.tick` and issues a generation token
  before the caller can reach an ``await`` — overlapping minimonitor refreshes
  (a documented reality, t1111_4) can never double-fire. The outcome calls
  (:meth:`confirm_fire` / :meth:`abort_fire`) consume only the live token.
- **Work latch.** A new episode needs positively *classified* agent work since
  the previous fire (:func:`classify_followed_change`), so widget
  selection-only redraws — which flip content-diff staleness — can never
  refire the loop.
- **Bounded-capture residual.** Both the staleness trigger and the classifier
  read a ``capture_lines``-bounded tail. Work whose settled tail is
  byte-identical AND whose scrollback did not grow is invisible — the loop
  simply does not fire for it; the manual "refetch and recheck" path remains
  available. (One ordinary plan revision measured live grew
  ``#{history_size}`` 28→61 and rewrote the content above the dialog, but
  that is a single rendering case, not proof of coverage — redraws confined
  to the visible region outside the retained tail can be substantive and
  still invisible.)

Readiness/composer/boundary patterns are version-sensitive terminal UI text
(pinned from live Claude Code 2.1.228 captures, 2026-08-12) and are maintained
in-place when an agent's UI wording changes — the ``prompt_patterns.py``
practice (t1474).
"""
from __future__ import annotations

import re
from collections.abc import Callable

try:
    from .ansi_utils import strip_ansi
    from .prompt_patterns import CLAUDE_PROCEED_LINE_RE, PROMPT_PATTERNS_BY_AGENT
except ImportError:  # imported flat (tests put MONITOR_DIR on sys.path)
    from ansi_utils import strip_ansi  # noqa: E402
    from prompt_patterns import (  # noqa: E402
        CLAUDE_PROCEED_LINE_RE,
        PROMPT_PATTERNS_BY_AGENT,
    )

import workflow_phase  # noqa: E402  (advisory phase seam — wording only, never a gate)


# Consecutive ticks of (awaiting_input AND stale) required before a fire.
# ~9s at the 3s refresh; only positive evidence counts (t1446 pattern).
DEBOUNCE_TICKS = 3

# Minimum gap between fires, across episodes. Bounds the worst case where
# every other guard is somehow satisfied repeatedly.
COOLDOWN_SECONDS = 45.0

# Controller states.
DISARMED = "disarmed"
WAITING = "waiting"
DELIVERING = "delivering"
FIRED = "fired"

# tick() actions.
ACTION_NONE = "none"
ACTION_FIRE = "fire"
ACTION_AUTO_DISARM = "auto_disarm"

# classify_followed_change results.
WORK = "work"
SELECTION_ONLY = "selection_only"
NO_CHANGE = "none"
UNKNOWN = "unknown"

# --- Loop-outcome reason codes (t1606) --------------------------------------
#
# Machine-readable identity for *why* the loop died or held. Before t1606 the
# four auto-disarm sites collapsed onto three prose messages, two of which were
# ambiguous across five distinct conditions -- so a live failure recorded
# nothing that could tell them apart, and every hypothesis about the spurious
# disarm was unfalsifiable in production.
#
# These are plain strings, matching the ACTION_* / SHADOW_* style above rather
# than an Enum (this module ships none), and they live HERE rather than in
# minimonitor_app because they are pure data: the module's no-I/O contract is
# what keeps the whole vocabulary unit-testable.
#
# DISARM_* is fatal -- the user's armed state is destroyed. HOLD_* is not: the
# delivery is aborted via ReviewLoopController.abort_fire and the loop stays
# armed. Which conditions earn which is argued in
# aidocs/framework/shadow_agent.md safety-contract items 6 and 9.

# Fatal: the loop is disarmed.
DISARM_AGENT_GONE = "agent_gone"
DISARM_SHADOW_GONE = "shadow_gone"
DISARM_NO_DETECTOR = "shadow_has_no_detector"
DISARM_NO_MONITOR = "no_tmux_monitor"
DISARM_PROMPT_WRITE_FAILED = "prompt_write_failed"
DISARM_ENTER_SEND_FAILED = "enter_send_failed"
DISARM_SUBMIT_UNCONFIRMED = "submit_unconfirmed"
DISARM_TEXT_NOT_IN_COMPOSER = "text_not_in_composer"

# Non-fatal: the delivery is aborted, the loop stays armed.
HOLD_PRE_ENTER_DIALOG = "pre_enter_dialog"
HOLD_PRE_ENTER_UNREADABLE = "pre_enter_unreadable"
HOLD_DELIVERY_SUPERSEDED = "delivery_superseded"
HOLD_SHADOW_NOT_SETTLED = "shadow_not_settled"

#: The single source of user-facing prose for every reason code.
#:
#: Each message must be TRUE of its own condition and of no other -- that is
#: the whole of t1606 Deliverable 3. The pre-t1606 code told a user whose shadow
#: pane merely could not be READ that "recheck text left in the shadow composer
#: -- submit or clear it there manually", while the composer was empty; the two
#: entries that still carry that wording are the only two where the text
#: demonstrably IS still sitting there (a write that succeeded, followed by an
#: Enter that provably did not land).
#:
#: `{subject}` is substituted by :func:`loop_reason_message`. Only
#: DISARM_NO_DETECTOR uses it.
LOOP_REASON_MESSAGES: dict[str, str] = {
    DISARM_AGENT_GONE:
        "the followed agent's pane is gone",
    DISARM_SHADOW_GONE:
        "the shadow pane is gone",
    DISARM_NO_DETECTOR:
        "shadow agent '{subject}' has no readiness detection",
    DISARM_NO_MONITOR:
        "no tmux monitor",
    DISARM_PROMPT_WRITE_FAILED:
        "could not write the recheck prompt to the shadow pane",
    DISARM_ENTER_SEND_FAILED:
        "recheck text left in the shadow composer — submit or clear it "
        "there manually",
    DISARM_SUBMIT_UNCONFIRMED:
        "recheck text left in the shadow composer — submit or clear it "
        "there manually",
    DISARM_TEXT_NOT_IN_COMPOSER:
        "the recheck prompt is not in the shadow composer — nothing was "
        "submitted",
    HOLD_PRE_ENTER_DIALOG:
        "shadow showed a dialog before the Enter — nothing sent",
    HOLD_PRE_ENTER_UNREADABLE:
        "could not read the shadow pane before the Enter — nothing sent",
    HOLD_DELIVERY_SUPERSEDED:
        "delivery superseded",
    HOLD_SHADOW_NOT_SETTLED:
        "shadow not settled at delivery time",
}

#: Short banner wording for the two holds that get a visible banner, budgeted
#: against `_LOOP_STATUS_ROWS` (2 rows at 38 usable columns => 76 cells).
#: A hold with no entry here records but paints nothing -- see
#: `minimonitor_app._loop_hold`.
LOOP_HOLD_BANNERS: dict[str, str] = {
    HOLD_PRE_ENTER_DIALOG: "⟳ holding: shadow showed a dialog — will retry",
    HOLD_PRE_ENTER_UNREADABLE: "⟳ holding: shadow pane unreadable — will retry",
}


def loop_reason_message(code: str, *, subject: str = "") -> str:
    """User-facing prose for a ``DISARM_*`` / ``HOLD_*`` code.

    The ONLY place loop-outcome prose is produced, so a message can never
    drift from the condition it describes -- the pre-t1606 strings were local
    variables inside ``_submit_shadow_prompt`` and were reused across
    conditions they were not true of.

    Total over garbage, like :func:`compose_recheck_prompt`: an unknown code
    yields a message naming the code rather than raising. A diagnostic path
    must not be the thing that crashes the TUI.
    """
    template = LOOP_REASON_MESSAGES.get(code)
    if template is None:
        return f"unrecognized loop reason '{code}'"
    return template.replace("{subject}", subject or "unknown")


def loop_hold_banner(code: str) -> str:
    """Banner line for a hold code, or ``""`` when it paints nothing."""
    return LOOP_HOLD_BANNERS.get(code, "")


class ReviewLoopController:
    """Decides fire/hold/disarm for the shadow auto-recheck.

    All inputs arrive through :meth:`tick`; the only outputs are the returned
    action string, the delivery token, and readable display state
    (:attr:`state`, :attr:`rounds_fired`, :attr:`holding_for_shadow`).
    """

    def __init__(self) -> None:
        self.state = DISARMED
        self.streak = 0
        self.work_seen = False
        self.rounds_fired = 0
        # Wall-independent (monotonic) instant of the last confirmed fire.
        # Survives disarm/re-arm on purpose: rapid L-L cycling must not
        # bypass the cooldown.
        self.fired_at: float | None = None
        # True when the debounced trigger is satisfied but the fire is held
        # only on shadow readiness — the banner renders "waiting for shadow
        # to settle" from this.
        self.holding_for_shadow = False
        # Supersession generation. Bumped on EVERY re-entry (arm, disarm,
        # reservation), so a stale confirm/abort from a superseded delivery
        # can never resurrect state.
        self._generation = 0
        self._delivery_token: int | None = None
        # Last observed non-None staleness, for the True->False EDGE that
        # consumes the work latch (a manual shadow refetch reviews any work
        # already observed). An edge rather than the level: the throttled
        # staleness cache can lag a same-tick work observation, and consuming
        # on every False would eat work the verdict predates.
        self._prev_stale: bool | None = None
        # Why the last tick-originated auto-disarm happened (t1606). Written
        # by tick(), read by the caller AFTER it observes ACTION_AUTO_DISARM.
        #
        # CLEARED BY arm() ONLY -- never by disarm(). That asymmetry is
        # load-bearing, not style. The disarm sequence is
        #   tick() -> self.disarm() -> return ACTION_AUTO_DISARM
        #     -> minimonitor_app._loop_auto_disarm -> ctrl.disarm() AGAIN
        # so a clear inside disarm() would wipe the code TWICE before anything
        # recorded it, and the ambiguity t1606 exists to remove would survive
        # the fix. arm() is the single clearing point, which also means every
        # lifecycle starts clean and no teardown can erase a reason in flight.
        self.last_disarm_reason: str | None = None

    # -- lifecycle ---------------------------------------------------------

    def arm(self, *, pending_work: bool) -> None:
        """Arm the loop.

        ``pending_work``: pass ``stale is True`` at the arm tick. An
        already-pending episode is covered by the explicit user action of
        arming; a fresh arm starts with the latch closed, so an arm-time
        selection-only redraw cannot produce a first redundant fire.
        """
        self._generation += 1
        self._delivery_token = None
        self.state = WAITING
        self.streak = 0
        self.rounds_fired = 0
        self.work_seen = bool(pending_work)
        self.holding_for_shadow = False
        # The single clearing point for the disarm reason -- see __init__.
        self.last_disarm_reason = None
        # Seed the edge state from the ARM-TIME observation, not from the
        # previous lifecycle (review rounds 3+4): ``pending_work=True`` IS a
        # positive "stale was True at arm" observation, so a manual shadow
        # refetch before the first service tick must form the True→False
        # edge and consume the pending latch. A fresh arm
        # (``pending_work=False``) carries no observation — None — so an
        # inherited True can never fake an edge.
        self._prev_stale = True if pending_work else None

    def disarm(self) -> None:
        """Disarm and retire any outstanding delivery token."""
        self._generation += 1
        self._delivery_token = None
        self.state = DISARMED
        self.streak = 0
        self.work_seen = False
        self.holding_for_shadow = False
        self._prev_stale = None  # edge state never crosses lifecycles

    @property
    def armed(self) -> bool:
        return self.state != DISARMED

    @property
    def generation(self) -> int:
        """Supersession generation (arm/disarm/reservation all bump it).

        The service snapshots this before its awaits and abandons post-await
        mutation when it changed — evidence classified against one lifecycle
        must never be injected into the next (review round 7).
        """
        return self._generation

    # -- per-tick decision -------------------------------------------------

    def tick(self, *, agent_present, shadow_present, awaiting_input,
             stale, work_signal, shadow_ready, modal_open,
             now: float) -> str:
        """One refresh-tick decision. Returns an ``ACTION_*`` string.

        ``ACTION_FIRE`` is a *reservation made synchronously here*: the
        controller is in DELIVERING and :attr:`delivery_token` names the
        reservation by the time this returns. The caller must route the
        delivery outcome to :meth:`confirm_fire` / :meth:`abort_fire`, or
        :meth:`disarm` on transport failure.
        """
        if self.state == DISARMED:
            return ACTION_NONE

        # Presence, tri-state: only a positively verified absence disarms.
        # None (capture failed / discovery indeterminate / lookup failed)
        # pauses — no advance, no reset, no disarm.
        if agent_present is False or shadow_present is False:
            self.disarm()
            # AFTER disarm(), never before: disarm() deliberately does not
            # clear this (see __init__), but writing it second means the order
            # is correct even if that ever changes. Two different failures --
            # the followed agent went away, or the shadow did -- which this
            # branch reported with one message before t1606.
            self.last_disarm_reason = (
                DISARM_AGENT_GONE if agent_present is False
                else DISARM_SHADOW_GONE)
            return ACTION_AUTO_DISARM
        if agent_present is None or shadow_present is None:
            return ACTION_NONE

        # Observations count even while a modal pauses firing: a sub-tick
        # work episode behind an open picker must still open the latch.
        if work_signal == WORK:
            self.work_seen = True
        # Read recency positively became current (True -> False edge): the
        # shadow read everything up to now — e.g. the user manually typed a
        # refetch — so any latched work is already reviewed. Consume it, or a
        # later selection-only redraw could reuse the stale latch and fire a
        # redundant round. Ordered AFTER the work observation above: a work
        # signal arriving on the same tick as the edge belongs to the state
        # the shadow just read.
        if stale is False and self._prev_stale is True:
            self.work_seen = False
        if stale is not None:
            self._prev_stale = stale

        if self.state == DELIVERING:
            # A delivery is in flight; no second permission (t1111_4 overlap).
            # The modal pause still applies to the PRESERVED streak (review
            # round 7): without this, modal → abort_fire would resume in
            # WAITING with a satisfied streak and re-reserve on the first
            # post-modal ready tick instead of re-debouncing.
            if modal_open:
                self.streak = 0
            return ACTION_NONE

        if self.state == FIRED:
            # Edge contract: only a positively observed stale == False (the
            # shadow acted and re-stamped) re-arms. None preserves. Runs
            # BEFORE the modal pause (review round 6): a modal inhibits
            # FIRING, never observation-driven state transitions — the only
            # False can arrive while a modal is open, and swallowing it
            # would wedge FIRED forever once staleness turns True again.
            if stale is False:
                self.state = WAITING
                self.streak = 0
            self.holding_for_shadow = False
            return ACTION_NONE

        # WAITING below. The modal pause inhibits the debounce and the fire
        # decision only — every observation above already ran.
        if modal_open:
            self.streak = 0
            self.holding_for_shadow = False
            return ACTION_NONE

        # WAITING: debounce on positive evidence only.
        if awaiting_input is True and stale is True:
            self.streak += 1
        else:
            self.streak = 0

        trigger = (
            self.streak >= DEBOUNCE_TICKS
            and self.work_seen
            and (self.fired_at is None
                 or now - self.fired_at >= COOLDOWN_SECONDS)
        )
        if trigger and shadow_ready is not True:
            # Hold: streak kept, fires on the first ready tick.
            self.holding_for_shadow = True
            return ACTION_NONE
        self.holding_for_shadow = False
        if trigger:
            # Reserve delivery synchronously, before any caller await.
            self._generation += 1
            self._delivery_token = self._generation
            self.state = DELIVERING
            return ACTION_FIRE
        return ACTION_NONE

    # -- delivery outcome --------------------------------------------------

    @property
    def delivery_token(self) -> int | None:
        return self._delivery_token

    def delivery_valid(self, token) -> bool:
        """True iff ``token`` is the live reservation. The fire path re-checks
        this after its pre-send capture await, before sending anything."""
        return (self.state == DELIVERING
                and token is not None
                and token == self._delivery_token)

    def confirm_fire(self, token, now: float) -> bool:
        """Delivery landed: FIRED, cooldown stamped, work latch closed."""
        if not self.delivery_valid(token):
            return False
        self._delivery_token = None
        self.state = FIRED
        self.streak = 0
        self.fired_at = now
        self.rounds_fired += 1
        self.work_seen = False
        return True

    def abort_fire(self, token) -> bool:
        """Pre-send revalidation refused (shadow busy): back to WAITING with
        the streak preserved — the next ready tick re-permits."""
        if not self.delivery_valid(token):
            return False
        self._delivery_token = None
        self.state = WAITING
        return True


# --- Shadow readiness (positive prompt detection) --------------------------
#
# Never inject into a busy shadow. Readiness is POSITIVE detection of the
# agent's idle input composer on a RAW (ANSI-carrying) capture tail — cleaned
# captures cannot work here: both Claude Code and Codex render their composer
# *placeholder hint* as dim text that strips to exactly what typed text strips
# to (measured live: at-rest hint vs typed text are indistinguishable after
# strip_ansi; the hint is dim `ESC[2m...ESC[0m`, typed text is plain).
#
# Three conjuncts, all required (hash stability alone is NEVER sufficient —
# it passes a shadow parked at a dialog or holding typed text):
#   (a) positive: the composer line is empty (bare prompt glyph or dim-only
#       hint);
#   (b) negative: no dialog/prompt pattern for the agent matches the tail
#       (a dialog is a different interaction — Enter there answers it), and
#       no working/streaming indicator is visible;
#   (c) hash stability: the raw tail unchanged >= 2 consecutive ticks,
#       computed by the caller (the animated indicator makes a streaming pane
#       hash-unstable, which is what blocks the streaming state's bare
#       composer from reading as ready).
#
# Per-agent measurements that shaped the generic detector (t1509):
#   * Claude's composer glyph is followed by an NBSP, which discriminates it
#     from `❯ 1. ...` option rows. Codex's is followed by a PLAIN space and is
#     shared with option rows AND echoed user messages, so the discriminator
#     there is the dim-strip test plus the structural option-row check below.
#   * A Codex dialog REPLACES the composer, so the positive half excludes
#     dialogs structurally — verified by running it with the pattern list
#     disabled over live permission / question-widget / update-prompt captures.
#   * Codex keeps its `• Running <cmd>` line on screen WHILE parked at a
#     permission dialog, so `dialog` must outrank `working` in `shadow_state`.
#
# Per-agent measurements that shaped the OpenCode sibling detector (t1520):
#   * OpenCode's composer is a `┃`-gutter BOX, not a glyph + text line, so it
#     does not fit the glyph+pad contract above; it gets its own positive half
#     and shares only the ORDER, via `_ordered_state`.
#   * Its permission dialog REPLACES the box (no border, no status row) -- but
#     the dialog is ALSO a `┃`-gutter box CONTAINING BLANK GUTTER ROWS, so a
#     naive "a blank gutter row exists" rule false-positives on it. The border
#     is what excludes it, verified with the pattern list emptied.
#   * There is NO SGR-dim anywhere in the OpenCode composer -- the placeholder
#     hint is a truecolor gray -- so `_DIM_SPAN_RE` does not transfer. The hint
#     is also gone after the first turn, so readiness must not depend on it.
#   * At-rest and working are INDISTINGUISHABLE inside the box; the only
#     discriminator is the `⬝⬝⬝⬝■■■■ esc interrupt` footer BELOW the border --
#     hence `_OPENCODE_MIN_LINES_BELOW_BORDER`, which fails closed when the
#     capture could not have shown it.
#   * Unlike Codex, OpenCode does NOT keep a working indicator up while parked
#     at a dialog (measured: the dialog replaces the footer region too), so the
#     dialog-outranks-working ordering is untestable for this agent.

# The composer line, after ANSI-strip: `❯` followed by NBSP and optional
# text. Widget option rows render `❯ 1. ...` with a plain space — the NBSP
# is the discriminator (measured on 2.1.228 captures).
_CLAUDE_COMPOSER_RE = re.compile("^\u276f(\\u00a0.*)?$")

# Dim span in the raw line: `ESC[2m ... ESC[0m` (or SGR22 dim-off). The
# composer hint is entirely dim; typed text is not.
_DIM_SPAN_RE = re.compile(r"\x1b\[2m.*?\x1b\[(?:0|22)m")

# Streaming/working indicator line (defense in depth beside hash
# instability): spinner glyph + word + ellipsis, or the esc-to-interrupt
# hint some states render.
_CLAUDE_SPINNER_RE = re.compile(
    r"(?m)^\s*[✽✳✶✻✢✺✹✸✷·∗+*]\s+\S+.*…|\(esc to interrupt\)"
)


# Codex's composer glyph, followed by an optional PLAIN-space-prefixed run.
# Unlike Claude there is no NBSP discriminator: option rows (`> 1. Yes, ...`)
# and echoed user messages share the glyph. They are excluded by the option-row
# check and the dim-strip test instead (measured on codex-cli 0.146.0).
_CODEX_COMPOSER_RE = re.compile("^›( .*)?$")

# A numbered option row rendered with the composer glyph. Structural evidence
# that a dialog -- not a composer -- occupies the bottom of the pane, and the
# reason Codex's UN-PATTERNED startup update prompt is still classified as a
# dialog rather than as a composer holding typed text.
_CODEX_OPTION_ROW_RE = re.compile("^›\\s*\\d+\\.\\s")

# Codex's working/streaming status line: `* Working (Ns * esc to interrupt)`
# or `* Running <cmd>`.
#
# DELIBERATELY carries no bare `esc to interrupt` alternation (unlike
# `_CLAUDE_SPINNER_RE`, whose parenthesised form Codex never renders): measured
# live, an unanchored `esc to interrupt` matches Codex's boot/tip text for
# ~0.5s. A false `working` there would CLEAR the caller's settle latch, so this
# anchors on the bullet status line only.
_CODEX_WORKING_RE = re.compile("(?m)^\\s*•\\s+(?:Working|Running)\\b")


# --- OpenCode (measured live, opencode 1.18.18 / GPT-5.4, 2026-08-16, t1520) --
#
# OpenCode's composer is a `┃`-gutter BOX, not a glyph + text line, so it does
# not fit `_composer_state`'s one-character-glyph contract at all -- hence the
# sibling positive half below rather than a widened shared one.
#
# Every row regex carries a leading `\s*`: the gutter is INDENTED, and the
# indent varies with layout (measured 23 columns on the splash screen, 2 after
# the first turn). None anchors on `$` -- OpenCode wraps a right-hand status
# column into the same physical lines, the same reason `opencode_question` in
# prompt_patterns.py uses `\s+` runs rather than fixed double spaces.

# A `┃`-gutter row; group 1 is the row's content.
_OPENCODE_GUTTER_RE = re.compile("^\\s*┃(.*)$")

# `╹▀▀▀…` -- the box's bottom border, and THE structural anchor. The permission
# dialog is also a `┃`-gutter box *containing blank gutter rows*, but it
# REPLACES the composer and renders no border, which is what excludes it
# without relying on pattern coverage (verified live with the pattern list
# emptied).
_OPENCODE_BOX_BOTTOM_RE = re.compile("^\\s*╹▀{3,}")

# The composer status row -- the LAST gutter row of the box, `<mode> · <model>
# · <effort>`. Deliberately generic over the mode token (it is user-switchable:
# build/plan) but NOT permissive: three `·`-separated fields INSIDE the gutter.
# The transcript renders `▣  Build · GPT-5.4` -- same mode word, same
# separator, no gutter and one field fewer -- so both the gutter and the second
# `·` are load-bearing against that near miss.
_OPENCODE_STATUS_ROW_RE = re.compile(
    "^\\s*┃\\s+\\S+\\s+·\\s+.+\\s+·\\s+\\S+\\s*$")

# The animated working footer, rendered one row BELOW the border:
# `⬝⬝⬝⬝■■■■  esc interrupt`. The glyph run ROTATES between the two block
# characters, so both are accepted in any order.
#
# Anchored on that glyph run, never on a bare `esc interrupt` alternation --
# the t1509 lesson: an unanchored form false-positives on boot/tip text, and a
# false `working` CLEARS the caller's settle latch.
_OPENCODE_WORKING_RE = re.compile(
    "(?m)^.*[⬝■]{2,}\\s+esc\\s+interrupt")

# The placeholder hint's truecolor gray span, the local replacement for
# `_DIM_SPAN_RE` -- OpenCode carries NO SGR-dim anywhere in the composer, so
# that discriminator does not transfer. The run ends at the next SGR escape.
#
# A SUBTRACTOR, never the positive anchor: the hint is present on a fresh
# session and GONE after the first turn (measured), so readiness must not
# depend on it. The triple is theme-derived; under a non-default theme this
# misses, the fresh-session hint reads as typed text, and the loop HOLDS until
# the first turn completes -- fail-safe, and self-healing thereafter.
_OPENCODE_HINT_SPAN_RE = re.compile(
    r"\x1b\[38;2;128;128;128m.*?(?=\x1b\[|$)")

# Minimum lines that must sit BELOW the box's bottom border for a would-be
# `ready` to be trustworthy. The working footer renders exactly ONE row below
# the border (measured: min == max == 1 across 287 live captures containing
# it), so with zero lines below it the footer CANNOT have been rendered.
#
# This is not hypothetical. Reproduced live at pane height 6: no room below the
# border, no footer, an empty box reading `ready`, and a byte-identical capture
# for 15+ consecutive samples -- so the hash-stability brake fails at the same
# time. An independent, non-screen channel (the opencode process tree's CPU
# time) confirmed the agent was working throughout. Boundary pinned in both
# directions: height 7 leaves 1 line below the border, renders the footer, and
# classifies `working` correctly.
_OPENCODE_MIN_LINES_BELOW_BORDER = 1


# `shadow_state` verdicts. Richer than the bool `shadow_prompt_ready` returns,
# because the caller's settle latch has to tell "an interaction is on screen"
# apart from "the agent is working" -- see minimonitor_app's post-interaction
# settle latch (t1509).
SHADOW_DIALOG = "dialog"
SHADOW_WORKING = "working"
SHADOW_READY = "ready"
SHADOW_BUSY = "busy"
SHADOW_UNKNOWN = "unknown"


def _ordered_state(raw_text: str, *, agent: str, positive, working_re) -> str:
    """The verdict ORDER, shared by every per-agent detector.

    ``positive(raw_text, plain) -> SHADOW_*`` is the per-agent **structural**
    half; everything around it is agent-invariant. Two shapes plug in here: the
    one-character-glyph composer line (`_composer_state`, Claude + Codex) and
    OpenCode's multi-row gutter box (`_opencode_box_state`, t1520).

    **Order is load-bearing** (measured, t1509): dialog patterns are checked
    FIRST, and ``working`` can only outrank a would-be ``ready``. Codex keeps
    its working/running line on screen while parked at a permission dialog, so
    a working-first order would report ``working`` for a pane that is still
    waiting on the user -- clearing the caller's settle latch at exactly the
    wrong moment.

    Living in ONE function is the point: with two structural halves the order
    would otherwise be duplicated, and a fix to one copy would silently not
    reach the other.
    """
    if not raw_text or not raw_text.strip():
        return SHADOW_UNKNOWN
    plain = strip_ansi(raw_text)

    # (b) Negative first: any dialog/prompt pattern anywhere in the tail means
    # a different interaction is pending (scan the whole tail, deliberately
    # wider than classify_content's bottom window).
    for pattern in PROMPT_PATTERNS_BY_AGENT.get(agent, []):
        if pattern.regex.search(plain):
            return SHADOW_DIALOG

    verdict = positive(raw_text, plain)
    if verdict == SHADOW_READY and working_re.search(plain):
        return SHADOW_WORKING
    return verdict


def _composer_state(raw_text: str, *, agent: str, composer_re,
                    working_re, pad: str, option_row_re=None) -> str:
    """Glyph-line composer classification (Claude Code, Codex CLI).

    Returns one of the ``SHADOW_*`` verdicts. ``pad`` is the run of characters
    stripped after the one-character prompt glyph (NBSP+space for Claude, a
    plain space for Codex). The verdict order lives in :func:`_ordered_state`;
    this function contributes only the positive half.

    Signature preserved verbatim: the negative-control tests call it directly
    with mutated regexes.
    """

    def positive(raw_text: str, plain: str) -> str:
        # Bottom-up, the composer line must exist and be empty. Falling off the
        # end without finding one is NOT ready and NOT merely unknown --
        # something else is occupying the pane, which the caller must treat as
        # an interaction.
        plain_lines = plain.splitlines()
        raw_lines = raw_text.splitlines()
        for idx in range(len(plain_lines) - 1, -1, -1):
            line = plain_lines[idx].rstrip()
            if not composer_re.match(line):
                continue
            if option_row_re is not None and option_row_re.match(line):
                return SHADOW_DIALOG  # an option row, not a composer
            after = line[1:].strip(pad)
            if not after:
                return SHADOW_READY  # bare composer
            # Visible text after the prompt char: typed text or the dim
            # placeholder hint. Decide from the raw styling -- hint is entirely
            # dim, typed text is not.
            raw_line = raw_lines[idx] if idx < len(raw_lines) else ""
            without_dim = strip_ansi(_DIM_SPAN_RE.sub("", raw_line)).rstrip()
            return (SHADOW_READY
                    if composer_re.match(without_dim)
                    and not without_dim[1:].strip(pad)
                    else SHADOW_BUSY)
        return SHADOW_DIALOG

    return _ordered_state(raw_text, agent=agent, positive=positive,
                          working_re=working_re)


def _claude_state(raw_text: str) -> str:
    return _composer_state(raw_text, agent="claude",
                           composer_re=_CLAUDE_COMPOSER_RE,
                           working_re=_CLAUDE_SPINNER_RE,
                           pad="  ")


def _codex_state(raw_text: str) -> str:
    return _composer_state(raw_text, agent="codex",
                           composer_re=_CODEX_COMPOSER_RE,
                           working_re=_CODEX_WORKING_RE,
                           pad=" ",
                           option_row_re=_CODEX_OPTION_ROW_RE)


def _opencode_box_state(raw_text: str, plain: str, *,
                        gutter_re=_OPENCODE_GUTTER_RE,
                        border_re=_OPENCODE_BOX_BOTTOM_RE,
                        status_re=_OPENCODE_STATUS_ROW_RE,
                        hint_span_re=_OPENCODE_HINT_SPAN_RE,
                        min_below=_OPENCODE_MIN_LINES_BELOW_BORDER) -> str:
    """OpenCode's positive half: a `┃`-gutter box closed by a `╹▀▀▀` border.

    The regexes are keyword parameters so the negative controls can substitute
    one without duplicating the function.
    """
    plain_lines = plain.splitlines()
    raw_lines = raw_text.splitlines()

    # 1. Bottom-up: the box's bottom border. Absent => something else occupies
    #    the pane (the dialog replaces the box entirely).
    border = next((i for i in range(len(plain_lines) - 1, -1, -1)
                   if border_re.match(plain_lines[i].rstrip())), None)
    if border is None:
        return SHADOW_DIALOG

    # 2. Window-sufficiency guard -- fail closed rather than assume. A `ready`
    #    is only trustworthy if the capture could have SHOWN a working footer,
    #    and the footer renders below the border. UNKNOWN (not BUSY, not
    #    DIALOG) is the honest verdict: unknowable, which the caller maps to
    #    None and never injects into, and which also arms its settle latch.
    if (len(plain_lines) - 1 - border) < min_below:
        return SHADOW_UNKNOWN

    # 3. The gutter rows are the contiguous `┃` run immediately ABOVE the
    #    border, so the dialog's blank gutter rows are never even reached.
    rows = []
    i = border - 1
    while i >= 0 and gutter_re.match(plain_lines[i]):
        rows.append(i)
        i -= 1
    if not rows:
        return SHADOW_DIALOG          # a border with no input area
    rows.reverse()

    # 4. The LAST gutter row is the status row (measured). It corroborates the
    #    border, so a stray border alone cannot produce a false `ready`.
    if not status_re.match(plain_lines[rows[-1]].rstrip()):
        return SHADOW_DIALOG
    content = rows[:-1]
    if not content:
        return SHADOW_DIALOG

    # 5. An empty box is ready. Visible content is either the gray placeholder
    #    hint or genuine typed text; decide from the RAW styling, since
    #    ANSI-stripping erases the difference. After the first turn the hint is
    #    gone entirely, so that case never reaches the subtraction at all.
    for idx in content:
        if not gutter_re.match(plain_lines[idx]).group(1).strip():
            continue
        raw_line = raw_lines[idx] if idx < len(raw_lines) else ""
        without_hint = strip_ansi(hint_span_re.sub("", raw_line))
        match = gutter_re.match(without_hint)
        if match is None or match.group(1).strip():
            return SHADOW_BUSY
    return SHADOW_READY


def _opencode_state(raw_text: str) -> str:
    return _ordered_state(raw_text, agent="opencode",
                          positive=_opencode_box_state,
                          working_re=_OPENCODE_WORKING_RE)


def _ready_from_state(state: str) -> bool | None:
    """Collapse a ``SHADOW_*`` verdict to the readiness tri-state."""
    if state == SHADOW_UNKNOWN:
        return None
    return state == SHADOW_READY


def _claude_ready(raw_text: str) -> bool | None:
    """Positive+negative readiness for a Claude Code shadow pane.

    ``raw_text`` is the raw ``capture-pane -p -e`` tail. Returns True only
    when an EMPTY composer is positively found and nothing dialog- or
    streaming-shaped is visible. Indeterminate reads return False/None --
    never True.
    """
    return _ready_from_state(_claude_state(raw_text))


def _codex_ready(raw_text: str) -> bool | None:
    """Positive+negative readiness for a Codex CLI shadow pane (t1509)."""
    return _ready_from_state(_codex_state(raw_text))


def _opencode_ready(raw_text: str) -> bool | None:
    """Positive+negative readiness for an OpenCode shadow pane (t1520)."""
    return _ready_from_state(_opencode_state(raw_text))


# Per-agent readiness dispatch. The shadow's agent is independently selectable
# (`E`), so a Claude followed pane can legitimately have a Codex or OpenCode
# shadow -- every such pairing is supported since t1520.
#
# As of t1520 NO member of `agent_keys.AGENT_KEYS` lacks a detector, so the
# arm-time refusal in minimonitor_app has no real-agent subject any more. It is
# kept, and exercised in tests with a synthetic key, because it is exactly what
# a FUTURE agent wired into AGENT_KEYS ahead of its detector will hit: agents
# without a detector must refuse at ARM time, not hold forever.
SHADOW_READY_DETECTORS = {
    "claude": _claude_ready,
    "codex": _codex_ready,
    "opencode": _opencode_ready,
}

# The same dispatch one layer down: the richer verdict the caller's settle
# latch needs. Keyed identically to SHADOW_READY_DETECTORS by construction,
# since each readiness function is derived from the state function here.
SHADOW_STATE_DETECTORS = {
    "claude": _claude_state,
    "codex": _codex_state,
    "opencode": _opencode_state,
}


# Agents whose FOLLOWED-pane change classification has a proven boundary
# strategy, and for which the auto-recheck loop may therefore be armed.
#
# Deliberately NOT `workflow_phase.live_tiers_available`: that answers "can an
# advisory phase hint be derived?", this answers "may an INJECTING loop be
# armed?". The separation is still real — an agent wired into AGENT_KEYS ahead
# of its own live evidence satisfies the first and must not satisfy the second.
#
# What earned each entry (each is a LIVE observation, not an inference):
#   claude   — t1159_2, the original loop.
#   codex    — t1518. Exec-approval boundary measured over 5 reps
#              (codex-cli 0.146.0): selection movement classifies
#              SELECTION_ONLY, work above the boundary classifies WORK.
#   opencode — t1518. Permission-dialog boundary measured over 5 reps
#              (1.18.18): selection movement leaves the STRIPPED capture
#              byte-identical (NO_CHANGE, never WORK), work above the boundary
#              classifies WORK.
# Both also confirmed live on their question widgets, and both arm-and-fire
# exactly one round with a real shadow. The measurement tables are in
# aiplans/archived/p1518_*.md.
#
# Adding a fourth agent is the same bar: measure, then widen. The completeness
# guard in tests/test_review_loop.py enforces that every kind an armed agent can
# report resolves to a boundary or is explicitly exempted.
REVIEW_LOOP_AGENTS: tuple[str, ...] = ("claude", "codex", "opencode")


def review_loop_agent_supported(agent: str) -> bool:
    """May the auto-recheck loop be armed for a followed pane running ``agent``?"""
    return (agent or "").strip().lower() in REVIEW_LOOP_AGENTS


# How long a shadow must present an uninterrupted empty composer after ANY
# on-screen interaction before the loop will fire into it.
#
# WALL-CLOCK SECONDS, deliberately not a tick count: the caller's committed
# evidence cadence is `max(1.0, 0.5 * refresh_seconds)` and `refresh_seconds`
# is user-configurable from two places (`ait minimonitor --interval` and
# `project_config.yaml: monitor.refresh_seconds`), flooring at 1.0s. A constant
# sized in ticks against the 1.5s default would expire ~33% early at
# `--interval 1`, reopening the window it exists to close.
#
# Sized by the t1509 pre-phase measurement: across 15 turn-level repetitions
# (permission dialog, question widget, startup update prompt) at 0.25s sampling,
# NO genuine injectable window reproduced — Codex keeps its working indicator up
# continuously through a turn, including across the dialog. The latch ships at
# the pre-registered floor anyway: a null result from five samples per kind is
# not proof of impossibility, and the measurement separately proved the RELEASE
# half is load-bearing (after the update prompt no work EVER follows, so a latch
# clearable only by a WORKING observation would wedge the loop permanently).
SHADOW_SETTLE_SECONDS = 2.0


# Wall-clock gap the delivery leaves between the literal prompt write, the Enter
# that submits it, and the capture that verifies the submission.
#
# NOT the same idea as SHADOW_SETTLE_SECONDS above, despite the neighbouring
# names: that one means "the shadow has been idle this long"; this one means
# "wait for a TUI to drain a pty write and repaint".
#
# Sized by the t1525 pre-phase sweep (2026-08-16, 150 live repetitions: every
# agent in SHADOW_READY_DETECTORS x d in {0, 0.25, 0.35, 0.5, 0.75} x 10, driven
# through the real gateway against claude 2.1.233 / codex-cli 0.146.0 /
# opencode 1.18.18). A value passes for an agent only at 10/10 on all three
# columns: the write visible in the composer at t+d (SHADOW_BUSY -- the sole
# state the delivery authorises an Enter on), the Enter actually submitting, and
# the composer non-BUSY at t+d afterwards.
#
# d=0 -- what shipped before t1525 -- FAILS for all three, in two distinct ways:
#   * codex submitted 0/10. It coalesces the input burst and consumes the Enter
#     as text, leaving the prompt unsubmitted while both send_keys return True.
#     This is the reported bug (t1523 item #4).
#   * claude and opencode submit fine at d=0, so the coalescing is Codex-
#     specific -- but neither has rendered the write yet at t+0 (preBUSY 0/10),
#     and claude's composer still SHOWED the text just after a successful submit
#     in 6/10 (postNonBUSY 4/10), which would have fired a spurious retry Enter.
#     So the drain is load-bearing for the readback on every agent, not just for
#     the Codex submit.
#
# The all-agent passing band is {0.25, 0.35, 0.5}; 0.75 is excluded (opencode
# 9/10 preBUSY -- an accumulated transcript matched a dialog pattern, the
# documented masking limitation, not a timing effect). Shipping the TOP of that
# band: the failure is one-sided and dramatic, 0.25 is the smallest value ever
# tested rather than a measured threshold, and the cost of margin is 1s of
# latency at most once per COOLDOWN_SECONDS.
#
# Unconditional rather than per-agent: at that price the delay is free, and one
# delivery path is simpler to reason about than two.
COMPOSER_DRAIN_SECONDS = 0.5

# Extra Enters allowed after a capture positively shows the composer STILL
# holding text. Bounded: each attempt costs 2 x the drain above plus two
# captures, so a wedged tmux (both captures burning the 3s capture timeout)
# holds DELIVERING for ~14s at worst. The controller cannot double-fire while
# there, and the banner reads "delivering…" throughout.
SHADOW_SUBMIT_RETRIES = 1


def shadow_state(raw_text: str | None, agent: str) -> str:
    """Classify a shadow pane's raw tail into one of the ``SHADOW_*`` verdicts.

    The richer view :func:`shadow_prompt_ready` is derived from, exposed
    because the caller's post-interaction settle latch must tell "an
    interaction is on screen" apart from "the agent is working" — only the
    latter is evidence the shadow genuinely resumed (t1509).

    ``raw_text`` None (capture failed) or an agent with no detector both yield
    ``SHADOW_UNKNOWN``: unknowable, never "fine to inject into".
    """
    if raw_text is None:
        return SHADOW_UNKNOWN
    detector = SHADOW_STATE_DETECTORS.get((agent or "").strip().lower())
    if detector is None:
        return SHADOW_UNKNOWN
    return detector(raw_text)


def shadow_prompt_ready(raw_text: str | None, agent: str,
                        hash_stable: bool) -> bool | None:
    """Three-part positive readiness; anything indeterminate is not-ready.

    ``raw_text``: raw ANSI-carrying tail of the shadow pane (None = capture
    failed). ``hash_stable``: raw tail unchanged >= 2 consecutive ticks,
    computed by the caller.

    Derived from :func:`shadow_state` so the two can never disagree about what
    a given capture means.
    """
    ready = _ready_from_state(shadow_state(raw_text, agent))
    if ready is not True:
        return ready
    if not hash_stable:
        return False
    return True


# --- Followed-pane change classification (work latch input) ----------------
#
# Distinguishes real agent output from widget selection-only redraws, which
# change captured content (and therefore content-diff staleness) without any
# work having happened. 'unknown' never satisfies the latch and never resets
# anything — tri-state discipline.

# Codex's exec-approval dialog header. `codex_permission` (footer, distance 1)
# and `codex_yes_proceed` (option row, distance 5) are the SAME dialog anchored
# at two distances, so both map to this one boundary.
#
# Measured live 2026-08-17 against codex-cli 0.146.0 at 120x30 (t1518): the line
# renders at index -13, exactly once per live frame, and is absent from at-rest
# and working frames — including at a repetition whose transcript already held
# five RESOLVED approval dialogs, so the header does not persist once the dialog
# closes. The only lines that change while the cursor moves are the option rows
# at -5/-4, strictly below it.
_CODEX_EXEC_APPROVAL_RE = re.compile(
    r"Would you like to run the following command\?"
)

# OpenCode's permission dialog header, measured live 2026-08-17 against 1.18.18
# at 120x30 (t1518): index -11, exactly once per live frame, absent from at-rest
# and working frames.
#
# Note what this row is FOR. OpenCode renders its option selection purely as
# ANSI styling, so a cursor move leaves the STRIPPED capture byte-identical and
# `classify_followed_change` returns NO_CHANGE before any boundary is consulted
# (verified against the raw capture, which does change). The selection direction
# was never the gap; this boundary exists for the other one — work performed
# ABOVE a live permission dialog, which classified UNKNOWN without it.
_OPENCODE_PERMISSION_RE = re.compile(r"Permission required")

# Claude's tool-permission dialog header — the dialog's default question text,
# rendered directly above the option list. Measured live 2026-08-17 against
# Claude Code 2.1.233 (t1540) over 7 pane geometries from 120x30 down to 120x6,
# 5 reps at 120x30 and 120x14: exactly once per live frame (47 dialog frames, 0
# violations), absent from every at-rest and working frame (32 frames, 0
# violations), and strictly above every line that changes during selection.
#
# ONE line, TWO kinds, because which kind is reported is decided by pane height:
#   * >=11 rows — the full three-option list fits, the question sits at -7,
#     outside _PROMPT_DETECTION_TAIL_LINES (6), and the bottom-anchored
#     `claude_help_bar` matches (t1474's structural prediction, confirmed live).
#   * <=9 rows — Claude truncates the option list to the selected row, which
#     lifts the question to -5, inside the tail window. `claude_proceed` is
#     listed first in PROMPT_PATTERNS_BY_AGENT and matching is first-wins, so it
#     becomes the reported kind.
# So `claude_proceed` is genuinely REACHABLE here — unlike codex_yes_proceed,
# which t1518 shipped unreached. Both rows are measured, neither is inferred.
#
# SCOPED BY MEASUREMENT, not by omission. `claude_help_bar` is Claude's generic
# blocked-on-input footer; only the tool-permission dialog was measured, so this
# boundary anchors only that dialog. On any other help-bar surface
# `_boundary_index` finds nothing, `_native_block_start` returns None, and
# `classify_followed_change` returns UNKNOWN — exactly as it did before this row
# existed. That is the conservative default preserved, NOT a rotted literal:
# a boundary-rot detector (t1542) must distinguish "scoped boundary, dialog
# never measured" from "shipped literal stopped matching its own dialog", or it
# will fire continuously on this row.
#
# This row is only load-bearing because t1540 also stabilised `claude_help_bar`
# in monitor/prompt_patterns.py; without that fix the kind flips mid-dialog and
# the classifier short-circuits to WORK before ever reaching this table.
#
# WHOLE-LINE anchor, and that is load-bearing rather than tidiness. The dialog's
# option rows are EDITABLE (Tab amends option 1), so a user who types this exact
# phrase into one puts a second copy of it BELOW the real header — and
# `_boundary_index` takes the LAST match, which would relocate the boundary onto
# an option row, i.e. onto a line that moves during selection. That is precisely
# the failure the B4 criterion exists to catch, reachable from user input rather
# than from CLI churn. Requiring the line to hold NOTHING but the question
# rejects the copy (it renders as ` ❯ 1. Yes, <typed text>`) while still matching
# the real header, verified identical on all 58 captured dialog frames. Same
# technique, and same reason, as `claude_trust_folder`'s "each option line holds
# nothing but its label" in monitor/prompt_patterns.py.
#
# The literal itself now lives in monitor/prompt_patterns.py and is SHARED with
# the `claude_proceed` prompt pattern (t1557): one line of one dialog, and the
# two layers must not be editable apart — they already drifted once, when t1540
# tightened this boundary and left the kind selector a substring. The boundary
# (block location) and the pattern (kind selection) remain different roles;
# `ClaudePermissionBoundaryTests.test_boundary_and_prompt_pattern_share_one_object`
# guards the sharing, so unpick it there first if they ever have to diverge.
_CLAUDE_PERMISSION_RE = CLAUDE_PROCEED_LINE_RE

# Top boundary line of native (chip-less) dialogs, per (agent, kind).
# The plan-approval dialog has no AskUserQuestion header chip, so
# workflow_phase.current_question_block cannot anchor it; this line —
# rendered directly above the options — is its measured stable boundary
# (live 2.1.228 capture, 2026-08-12).
NATIVE_DIALOG_BOUNDARIES: dict[tuple[str, str], re.Pattern] = {
    ("claude", "claude_plan_approval"): re.compile(
        r"written up a plan and is ready to execute|Would you like to proceed\?"
    ),
    # Same dialog, two kinds selected by pane height — see _CLAUDE_PERMISSION_RE.
    ("claude", "claude_help_bar"): _CLAUDE_PERMISSION_RE,
    ("claude", "claude_proceed"): _CLAUDE_PERMISSION_RE,
    ("codex", "codex_permission"): _CODEX_EXEC_APPROVAL_RE,
    # Shipped despite never being observed as the reported kind on 0.146.0
    # (0/23 live captures): the footer that `codex_permission` matches sits at
    # distance 1 and matching is first-wins, and nothing renders below it. The
    # boundary's B1/B2/B3 evidence is the same dialog frame, so the row is
    # correct if a future version ever surfaces this kind, and omitting it would
    # mean silently degrading to UNKNOWN in exactly that case (t1518).
    ("codex", "codex_yes_proceed"): _CODEX_EXEC_APPROVAL_RE,
    ("opencode", "opencode_permission"): _OPENCODE_PERMISSION_RE,
}

# Native dialogs delimited by SHAPE rather than by a header line, keyed like
# NATIVE_DIALOG_BOUNDARIES. Same split, and for the same reason, as
# workflow_phase.QUESTION_BLOCK_BOUNDARIES / QUESTION_BLOCK_STRATEGIES: a regex
# matching a gutter glyph alone would match EVERY line of the block, including
# an earlier already-answered one higher in the tail.
#
# Empty today and defined anyway. `classify_followed_change` consults it before
# the regex table on every native-dialog kind, so a conditionally-defined symbol
# would be a NameError whenever no agent needed it, and would push callers into
# `globals().get` crutches. An empty dict is a live miss followed by a regex
# hit, not a dead branch.
#
# OpenCode was the candidate (its permission dialog sits inside a `┃`-gutter run
# that workflow_phase._opencode_block_start already locates) and was measured
# EQUIVALENT to the phrase in t1518: the single line between the gutter top
# (-12) and the header (-11) never changes during selection. The tie went to the
# simpler mechanism. Reuse `_opencode_block_start` — do not fork the scan.
NATIVE_DIALOG_STRATEGIES: dict[
    tuple[str, str], Callable[[list[str]], int | None]] = {}

# (agent, kind) pairs that deliberately have NO boundary, with the reason.
# Consumed by the completeness guard in tests/test_review_loop.py: a kind that
# resolves through neither strategy table and is not listed here is an
# OMISSION and fails the guard.
#
# Keyed per AGENT, including for kinds contributed by the cross-agent
# PROMPT_PATTERNS_BY_AGENT["all"] group — a generic prompt can legitimately need
# a different boundary per agent, so it is resolved or exempted once per agent
# rather than globally.
DELIBERATELY_UNANCHORED_KINDS: dict[tuple[str, str], str] = {
    ("opencode", "opencode_palette"):
        "overlay, not a dialog: it renders ~21 lines up, outside "
        "_PROMPT_DETECTION_TAIL_LINES, so it is never a followed-pane "
        "awaiting_input_kind (t1520)",
    # `claude_help_bar` and `claude_proceed` were exempted here as "no measured
    # boundary (pre-t1518)" and are now anchored — t1540 measured both live.
    #
    # `claude_trust_folder` stays, and the reason is now MEASURED rather than a
    # placeholder: the kind is not reported at all on 2.1.233, so no boundary
    # for it could ever be consulted. Two independent causes, either fatal on
    # its own (t1540, live capture on a fresh untrusted directory):
    #   1. wording — the confirm/cancel options render as a NUMBERED list, while
    #      the pattern requires each label to follow the pointer directly and to
    #      be the whole line;
    #   2. geometry — the trust screen is the pre-TUI boot screen and renders
    #      TOP-aligned; at 120x30 its options sit at -17/-16 and its footer at
    #      -14, so the whole dialog is outside _PROMPT_DETECTION_TAIL_LINES (6)
    #      and every one of the last six lines is empty.
    # That is a prompt-pattern defect, not a boundary gap: fixing it belongs in
    # monitor/prompt_patterns.py, and until it is fixed this exemption is
    # correct rather than merely conservative.
    ("claude", "claude_trust_folder"):
        "kind never reported on 2.1.233 — numbered option labels no longer "
        "match the pattern AND the pre-TUI trust screen renders top-aligned, "
        "outside _PROMPT_DETECTION_TAIL_LINES; no boundary can be consulted "
        "for a kind that is never detected (t1540)",
}


def _boundary_index(lines: list[str], pattern: re.Pattern) -> int | None:
    for idx in range(len(lines) - 1, -1, -1):
        if pattern.search(lines[idx]):
            return idx
    return None


def _native_block_start(lines: list[str], agent_key: str,
                        kind: str) -> int | None:
    """Index starting the live native dialog block, or ``None``.

    Strategy table first, regex table second — the same precedence
    ``workflow_phase.current_question_block`` uses, so the two block-boundary
    mechanisms cannot disagree about which wins. ``None`` means "could not
    locate", never a default index.
    """
    strategy = NATIVE_DIALOG_STRATEGIES.get((agent_key, kind))
    if strategy is not None:
        return strategy(lines)
    boundary = NATIVE_DIALOG_BOUNDARIES.get((agent_key, kind))
    if boundary is None:
        return None
    return _boundary_index(lines, boundary)


def native_dialog_anchored(agent_key: str, kind: str) -> bool:
    """Does ``(agent_key, kind)`` resolve through either native-dialog table?"""
    key = (agent_key, kind)
    return key in NATIVE_DIALOG_STRATEGIES or key in NATIVE_DIALOG_BOUNDARIES


def classify_followed_change(prev_content: str | None, prev_kind: str,
                             curr_content: str, curr_kind: str,
                             awaiting_input: bool, agent: str,
                             prev_history_size: int | None = None,
                             curr_history_size: int | None = None,
                             prev_size: tuple[int, int] | None = None,
                             curr_size: tuple[int, int] | None = None) -> str:
    """Classify the followed pane's inter-tick change.

    Returns ``WORK`` / ``SELECTION_ONLY`` / ``NO_CHANGE`` / ``UNKNOWN``.
    Contents are the raw tick captures (``snap.content``); ANSI is stripped
    here so styling churn never reads as change.
    """
    # A pane resize invalidates BOTH evidence channels for this comparison:
    # tmux reflow rewraps content (a spurious diff) and re-buckets lines
    # into history (#{history_size} measured moving 471->491 on a plain
    # 120x30 -> 50x10 resize with no output at all). Conservative UNKNOWN;
    # the caller's baseline update re-aligns the next comparison.
    #
    # ACCEPTED TRADEOFF (documented, review round 3): output that arrives in
    # the SAME capture as the resize is absorbed — there is no valid signal
    # across a reflow (comparing against the pre-resize baseline would trade
    # this false negative for rewrap false positives, and the history delta
    # is equally polluted). Any further output on the next stable-geometry
    # tick classifies normally; only work confined entirely to the resize
    # tick, with nothing after, is lost — the same shape as the
    # bounded-capture residual, and covered by the same manual fallback.
    if (prev_size is not None and curr_size is not None
            and prev_size != curr_size):
        return UNKNOWN

    # Durable scrollback-growth signal: even an identical bounded tail is
    # WORK if lines scrolled into history (a long revision can scroll
    # entirely past the retained window). Measured live: selection
    # navigation leaves #{history_size} unchanged; answering/revising grows
    # it. A shrink (clear-history / pane recycle) contributes nothing. Only
    # meaningful at constant geometry — the resize guard above runs first.
    if (prev_history_size is not None and curr_history_size is not None
            and curr_history_size > prev_history_size):
        return WORK

    if prev_content is None:
        return UNKNOWN
    prev_plain = strip_ansi(prev_content)
    curr_plain = strip_ansi(curr_content)
    if prev_plain == curr_plain:
        return NO_CHANGE
    if awaiting_input is not True:
        return WORK  # output produced outside any recognized prompt
    if (prev_kind or "") != (curr_kind or ""):
        return WORK  # a different dialog kind = progression

    agent_key = (agent or "").strip().lower()
    prev_lines = prev_plain.splitlines()
    curr_lines = curr_plain.splitlines()

    if curr_kind in workflow_phase.QUESTION_WIDGET_KINDS.get(agent_key, ()):
        # Pass the agent: each CLI delimits its question block differently since
        # t1467, and measuring a Codex pane against Claude's chip would silently
        # return None (UNKNOWN) instead of classifying it.
        start_prev = workflow_phase.current_question_block(prev_lines, agent_key)
        start_curr = workflow_phase.current_question_block(curr_lines, agent_key)
        if start_prev is None or start_curr is None:
            return UNKNOWN
        if prev_lines[:start_prev] != curr_lines[:start_curr]:
            return WORK  # scrollback above the live widget grew/changed
        return SELECTION_ONLY

    if native_dialog_anchored(agent_key, curr_kind or ""):
        # Both mechanisms return an index into the same line list, so the
        # comparison below is shared verbatim between them.
        start_prev = _native_block_start(prev_lines, agent_key, curr_kind or "")
        start_curr = _native_block_start(curr_lines, agent_key, curr_kind or "")
        if start_prev is None or start_curr is None:
            return UNKNOWN
        if prev_lines[:start_prev] != curr_lines[:start_curr]:
            return WORK
        return SELECTION_ONLY

    return UNKNOWN  # prompt kind with no boundary strategy — conservative


# --- Recheck prompt composition --------------------------------------------


def compose_recheck_prompt(phase: str | None,
                           expected_round: int | None) -> str:
    """Single-line recheck prompt for injection into the shadow pane.

    Total over all inputs: any unrecognized/None phase gets the generic
    wording (phase pre-selects WORDING only — it never gates firing; the
    advisory-only contract, t1311/t1420). The leading "refetch and recheck
    [round N]" is verbatim the routing trigger of the shadow skill's Step 3
    re-review entry (t1493), so the injected line deterministically re-enters
    the review sub-procedure and re-emits the concern block.
    """
    round_part = ""
    if isinstance(expected_round, int) and expected_round > 0:
        round_part = f" round {expected_round}"
    if phase == "PLAN":
        tail = ("re-run the plan-challenge review sub-procedure end to end "
                "and emit the concern block")
    elif phase in ("IMPLEMENT", "POSTIMPL"):
        tail = ("re-run the impl-challenge review sub-procedure end to end "
                "and emit the concern block")
    else:
        tail = "run the next review round end to end and emit the concern block"
    text = f"refetch and recheck{round_part}: {tail}"
    return " ".join(text.split())  # guaranteed single line, no newlines
