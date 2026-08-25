"""Unit tests for the shadow auto-recheck decision core (t1159_2).

Everything here is pure — no tmux, no Textual, no I/O. The load-bearing
contracts, each with a control so a green run cannot be vacuous:

- the controller is EDGE-driven (no second fire while FIRED, even with
  ``stale True`` forever; only an observed ``stale False`` re-arms);
- ``'fire'`` is a synchronous DELIVERING reservation consumed by exactly one
  ``confirm_fire``/``abort_fire`` with the live token (overlap hardening);
- presence is tri-state: only verified absence disarms, indeterminate pauses;
- the work latch opens only on classified WORK — widget selection-only
  redraws (which flip content-diff staleness) can never refire the loop;
- readiness is three-part positive detection on RAW captures — the dim
  composer hint strips identically to typed text, so these fixtures are real
  ANSI-carrying captures (see ``review_loop_fixtures``);
- ``compose_recheck_prompt`` is total over garbage and always single-line,
  leading with the t1493 routing trigger.
"""

from __future__ import annotations

import contextlib
import functools
import os
import sys
import re
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
sys.path.insert(0, str(SCRIPTS_DIR / "monitor"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_loop as rl  # noqa: E402
import review_loop_fixtures as fx  # noqa: E402
import prompt_patterns as pp  # noqa: E402
# t1540: the Claude permission-dialog tests assert which KIND production
# reports, not just how a given kind classifies — the two boundary rows are
# selected by pane geometry, and a defect in detection short-circuits the
# classifier ahead of any boundary lookup.
import monitor_core as mc  # noqa: E402
import workflow_phase as wp  # noqa: E402
from ansi_utils import strip_ansi as strip  # noqa: E402


@contextlib.contextmanager
def patched_claude_patterns(patterns):
    """Temporarily replace the claude prompt-pattern group.

    Mutates the shipped dict in place rather than rebinding a name, for the same
    reason `patched_strategy` does: `review_loop` imported the dict object
    itself, so production reads through this very mapping.
    """
    prev = pp.PROMPT_PATTERNS_BY_AGENT["claude"]
    pp.PROMPT_PATTERNS_BY_AGENT["claude"] = patterns
    try:
        yield
    finally:
        pp.PROMPT_PATTERNS_BY_AGENT["claude"] = prev


@contextlib.contextmanager
def patched_strategy(key, fn):
    """Temporarily register a NATIVE_DIALOG_STRATEGIES entry.

    Mutates the shipped dict rather than rebinding the name: production reads
    the module global, so a rebind would leave the real lookup untouched and
    the test would pass without exercising anything.
    """
    had = key in rl.NATIVE_DIALOG_STRATEGIES
    prev = rl.NATIVE_DIALOG_STRATEGIES.get(key)
    rl.NATIVE_DIALOG_STRATEGIES[key] = fn
    try:
        yield
    finally:
        if had:
            rl.NATIVE_DIALOG_STRATEGIES[key] = prev
        else:
            rl.NATIVE_DIALOG_STRATEGIES.pop(key, None)


def make_ready_kwargs(**overrides):
    """A tick input set that satisfies every fire condition."""
    kwargs = dict(
        agent_present=True, shadow_present=True, awaiting_input=True,
        stale=True, work_signal=rl.NO_CHANGE, shadow_ready=True,
        modal_open=False, now=1000.0,
    )
    kwargs.update(overrides)
    return kwargs


def drive_to_fire(ctrl, now=1000.0, **overrides):
    """Debounce the controller to the fire tick; returns the last action."""
    action = rl.ACTION_NONE
    for i in range(rl.DEBOUNCE_TICKS):
        action = ctrl.tick(**make_ready_kwargs(now=now + i, **overrides))
    return action


class ControllerLifecycleTests(unittest.TestCase):
    def test_disarmed_is_inert(self):
        ctrl = rl.ReviewLoopController()
        for _ in range(5):
            self.assertEqual(ctrl.tick(**make_ready_kwargs()), rl.ACTION_NONE)
        self.assertEqual(ctrl.state, rl.DISARMED)

    def test_debounce_requires_exactly_three_positive_ticks(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1)), rl.ACTION_NONE)
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=2)), rl.ACTION_NONE)
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=3)), rl.ACTION_FIRE)

    def test_negative_or_none_resets_streak(self):
        for breaker in (dict(awaiting_input=False), dict(awaiting_input=None),
                        dict(stale=False), dict(stale=None)):
            ctrl = rl.ReviewLoopController()
            ctrl.arm(pending_work=True)
            ctrl.tick(**make_ready_kwargs(now=1))
            ctrl.tick(**make_ready_kwargs(now=2))
            ctrl.tick(**make_ready_kwargs(now=3, **breaker))
            # Streak was reset: two more positives are not enough... (the
            # first re-opens the work latch, which the stale=False breaker
            # legitimately consumed via the currency edge — see
            # WorkLatchTests.test_manual_refetch_edge_consumes_the_latch)
            self.assertEqual(ctrl.tick(**make_ready_kwargs(
                now=4, work_signal=rl.WORK)), rl.ACTION_NONE, breaker)
            self.assertEqual(ctrl.tick(**make_ready_kwargs(now=5)),
                             rl.ACTION_NONE, breaker)
            # ...the third is.
            self.assertEqual(ctrl.tick(**make_ready_kwargs(now=6)),
                             rl.ACTION_FIRE, breaker)

    def test_edge_contract_no_second_fire_while_stale_stays_true(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        self.assertEqual(drive_to_fire(ctrl), rl.ACTION_FIRE)
        self.assertTrue(ctrl.confirm_fire(ctrl.delivery_token, 1002.0))
        self.assertEqual(ctrl.state, rl.FIRED)
        # stale True forever + work signals: never a second fire.
        for i in range(20):
            action = ctrl.tick(**make_ready_kwargs(
                now=2000 + i, work_signal=rl.WORK))
            self.assertEqual(action, rl.ACTION_NONE)
            self.assertEqual(ctrl.state, rl.FIRED)

    def test_stale_false_rearms_and_none_does_not(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        ctrl.confirm_fire(ctrl.delivery_token, 1002.0)
        ctrl.tick(**make_ready_kwargs(now=1010, stale=None))
        self.assertEqual(ctrl.state, rl.FIRED)  # None preserves
        ctrl.tick(**make_ready_kwargs(now=1011, stale=False))
        self.assertEqual(ctrl.state, rl.WAITING)  # False re-arms

    def test_cooldown_blocks_an_immediate_second_episode(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl, now=1000.0)
        ctrl.confirm_fire(ctrl.delivery_token, 1002.0)
        # Re-arm on the currency edge FIRST, then observe new work on a
        # later tick — work on the edge tick itself is covered by the
        # shadow's read and rightly consumed (currency-edge rule).
        ctrl.tick(**make_ready_kwargs(now=1003, stale=False))
        ctrl.tick(**make_ready_kwargs(now=1003.5, work_signal=rl.WORK))
        # Trigger re-satisfied within the cooldown window: held.
        self.assertEqual(drive_to_fire(ctrl, now=1004), rl.ACTION_NONE)
        # The streak survived the hold, so the FIRST tick past the cooldown
        # fires without re-debouncing.
        self.assertEqual(
            ctrl.tick(**make_ready_kwargs(now=1002.0 + rl.COOLDOWN_SECONDS)),
            rl.ACTION_FIRE)

    def test_modal_pauses_streak_without_disarm(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        ctrl.tick(**make_ready_kwargs(now=1))
        ctrl.tick(**make_ready_kwargs(now=2))
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=3, modal_open=True)),
                         rl.ACTION_NONE)
        self.assertTrue(ctrl.armed)
        # Streak was reset by the modal tick.
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=4)), rl.ACTION_NONE)
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=5)), rl.ACTION_NONE)
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=6)), rl.ACTION_FIRE)

    def test_modal_does_not_swallow_the_fired_rearm_edge(self):
        # Review round 6 reproduction: the ONLY stale=False arrives while a
        # modal is open. The modal must inhibit firing, not the FIRED
        # re-arm — swallowing the edge (with _prev_stale already advanced)
        # wedged FIRED forever once staleness turned True again.
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        ctrl.confirm_fire(ctrl.delivery_token, 1002.0)
        ctrl.tick(**make_ready_kwargs(now=1003, stale=False,
                                      modal_open=True))
        self.assertEqual(ctrl.state, rl.WAITING)
        # The loop completes a later episode normally.
        base = 1002.0 + rl.COOLDOWN_SECONDS
        ctrl.tick(**make_ready_kwargs(now=base, work_signal=rl.WORK))
        ctrl.tick(**make_ready_kwargs(now=base + 1))
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=base + 2)),
                         rl.ACTION_FIRE)

    def test_shadow_busy_holds_with_streak_preserved(self):
        for busy in (False, None):
            ctrl = rl.ReviewLoopController()
            ctrl.arm(pending_work=True)
            self.assertEqual(drive_to_fire(ctrl, shadow_ready=busy),
                             rl.ACTION_NONE, busy)
            self.assertTrue(ctrl.holding_for_shadow, busy)
            # First ready tick fires — the streak was preserved.
            self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1010)),
                             rl.ACTION_FIRE, busy)
            self.assertFalse(ctrl.holding_for_shadow, busy)


class DeliveringModalTests(unittest.TestCase):
    def test_modal_during_delivery_forces_a_redebounce_after_abort(self):
        # Review round 7 reproduction: DELIVERING with the streak preserved,
        # a modal tick, then a pre-send abort — the first post-modal ready
        # tick must NOT re-reserve; the debounce restarts.
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        self.assertEqual(ctrl.state, rl.DELIVERING)
        ctrl.tick(**make_ready_kwargs(now=1005, modal_open=True))
        self.assertTrue(ctrl.abort_fire(ctrl.delivery_token))
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1006)),
                         rl.ACTION_NONE)  # re-debouncing, not firing
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1007)),
                         rl.ACTION_NONE)
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1008)),
                         rl.ACTION_FIRE)

    def test_abort_without_modal_still_retries_on_the_next_ready_tick(self):
        # Positive control: the round-1 hold contract is unchanged when no
        # modal intervened.
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        ctrl.abort_fire(ctrl.delivery_token)
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1005)),
                         rl.ACTION_FIRE)


class PresenceTriStateTests(unittest.TestCase):
    def test_verified_absence_disarms(self):
        for absent in (dict(agent_present=False), dict(shadow_present=False)):
            ctrl = rl.ReviewLoopController()
            ctrl.arm(pending_work=True)
            self.assertEqual(ctrl.tick(**make_ready_kwargs(**absent)),
                             rl.ACTION_AUTO_DISARM, absent)
            self.assertEqual(ctrl.state, rl.DISARMED, absent)

    def test_indeterminate_presence_pauses_and_preserves(self):
        for indet in (dict(agent_present=None), dict(shadow_present=None)):
            ctrl = rl.ReviewLoopController()
            ctrl.arm(pending_work=True)
            ctrl.tick(**make_ready_kwargs(now=1))
            ctrl.tick(**make_ready_kwargs(now=2))
            # Indeterminate tick: armed, streak NOT reset, no disarm.
            self.assertEqual(ctrl.tick(**make_ready_kwargs(now=3, **indet)),
                             rl.ACTION_NONE, indet)
            self.assertTrue(ctrl.armed, indet)
            # A following healthy tick completes the episode: the streak
            # survived the gap (2 positives + this one = fire).
            self.assertEqual(ctrl.tick(**make_ready_kwargs(now=4)),
                             rl.ACTION_FIRE, indet)

    def test_indeterminate_presence_retires_nothing_mid_delivery(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        token = ctrl.delivery_token
        ctrl.tick(**make_ready_kwargs(now=1005, shadow_present=None))
        self.assertTrue(ctrl.delivery_valid(token))

    def test_verified_absence_retires_inflight_delivery(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        token = ctrl.delivery_token
        self.assertEqual(
            ctrl.tick(**make_ready_kwargs(now=1005, shadow_present=False)),
            rl.ACTION_AUTO_DISARM)
        self.assertFalse(ctrl.delivery_valid(token))
        self.assertFalse(ctrl.confirm_fire(token, 1006.0))


class DeliveryReservationTests(unittest.TestCase):
    def test_fire_enters_delivering_synchronously(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        self.assertEqual(drive_to_fire(ctrl), rl.ACTION_FIRE)
        self.assertEqual(ctrl.state, rl.DELIVERING)
        self.assertIsNotNone(ctrl.delivery_token)

    def test_interleaved_tick_grants_no_second_permission(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        # A second overlapping service invocation ticks between reservation
        # and outcome: it must see DELIVERING and grant nothing.
        for i in range(3):
            self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1010 + i)),
                             rl.ACTION_NONE)
        self.assertEqual(ctrl.state, rl.DELIVERING)

    def test_confirm_consumes_only_the_live_token(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        token = ctrl.delivery_token
        self.assertTrue(ctrl.confirm_fire(token, 1002.0))
        self.assertEqual(ctrl.state, rl.FIRED)
        self.assertEqual(ctrl.rounds_fired, 1)
        self.assertFalse(ctrl.work_seen)  # latch closed by the fire
        # Replaying the same token is a no-op.
        self.assertFalse(ctrl.confirm_fire(token, 1003.0))
        self.assertEqual(ctrl.rounds_fired, 1)

    def test_abort_returns_to_waiting_with_streak_preserved(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        token = ctrl.delivery_token
        self.assertTrue(ctrl.abort_fire(token))
        self.assertEqual(ctrl.state, rl.WAITING)
        # Streak survived the aborted delivery: one ready tick re-permits.
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1010)),
                         rl.ACTION_FIRE)

    def test_stale_token_after_disarm_is_inert(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        token = ctrl.delivery_token
        ctrl.disarm()
        self.assertFalse(ctrl.delivery_valid(token))
        self.assertFalse(ctrl.confirm_fire(token, 1002.0))
        self.assertFalse(ctrl.abort_fire(token))
        self.assertEqual(ctrl.state, rl.DISARMED)
        # Even after re-arming, the retired token stays dead (generation).
        ctrl.arm(pending_work=True)
        self.assertFalse(ctrl.confirm_fire(token, 1003.0))
        self.assertEqual(ctrl.state, rl.WAITING)


class WorkLatchTests(unittest.TestCase):
    def _fired(self):
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        drive_to_fire(ctrl)
        ctrl.confirm_fire(ctrl.delivery_token, 1002.0)
        # Shadow acted: re-arm the edge.
        ctrl.tick(**make_ready_kwargs(now=1003, stale=False))
        self.assertEqual(ctrl.state, rl.WAITING)
        return ctrl

    def test_selection_only_redraws_never_refire(self):
        ctrl = self._fired()
        # Navigation flips staleness True again, awaiting stays True, every
        # change classifies selection_only: no second permission, ever.
        base = 1002.0 + rl.COOLDOWN_SECONDS  # cooldown out of the way
        for i in range(20):
            action = ctrl.tick(**make_ready_kwargs(
                now=base + i, work_signal=rl.SELECTION_ONLY))
            self.assertEqual(action, rl.ACTION_NONE, i)

    def test_one_work_tick_reopens_the_latch(self):
        ctrl = self._fired()
        base = 1002.0 + rl.COOLDOWN_SECONDS
        # Positive control for the test above: identical sequence except one
        # WORK classification (never any awaiting_input False sample —
        # the sub-tick episode shape).
        ctrl.tick(**make_ready_kwargs(now=base, work_signal=rl.WORK))
        ctrl.tick(**make_ready_kwargs(now=base + 1))
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=base + 2)),
                         rl.ACTION_FIRE)

    def test_unknown_and_none_leave_the_latch_unchanged(self):
        ctrl = self._fired()
        base = 1002.0 + rl.COOLDOWN_SECONDS
        for signal in (rl.UNKNOWN, rl.NO_CHANGE):
            for i in range(5):
                self.assertEqual(
                    ctrl.tick(**make_ready_kwargs(now=base + i,
                                                  work_signal=signal)),
                    rl.ACTION_NONE, signal)

    def test_fresh_arm_requires_work_but_pending_arm_does_not(self):
        fresh = rl.ReviewLoopController()
        fresh.arm(pending_work=False)
        self.assertEqual(drive_to_fire(fresh,
                                       work_signal=rl.SELECTION_ONLY),
                         rl.ACTION_NONE)
        pending = rl.ReviewLoopController()
        pending.arm(pending_work=True)
        self.assertEqual(drive_to_fire(pending,
                                       work_signal=rl.SELECTION_ONLY),
                         rl.ACTION_FIRE)

    def test_manual_refetch_edge_consumes_the_latch(self):
        # Review round 2 (t1159_2 impl review): work is observed while the
        # debounce is running, the user MANUALLY refetches (stale True ->
        # False edge), then only selection redraws follow. The latched work
        # was already reviewed — the loop must not fire on the stale latch.
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=False)
        ctrl.tick(**make_ready_kwargs(now=1, work_signal=rl.WORK))
        self.assertTrue(ctrl.work_seen)
        # Manual refetch: read recency positively becomes current.
        ctrl.tick(**make_ready_kwargs(now=2, stale=False))
        self.assertFalse(ctrl.work_seen)
        # Selection-only churn flips staleness True again: never a fire.
        for i in range(10):
            self.assertEqual(
                ctrl.tick(**make_ready_kwargs(
                    now=3 + i, work_signal=rl.SELECTION_ONLY)),
                rl.ACTION_NONE)

    def test_same_tick_work_and_false_edge_is_consumed(self):
        # The edge's verdict is computed from the same refresh's snapshot,
        # so work arriving on the edge tick IS covered by the shadow's read.
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=False)
        ctrl.tick(**make_ready_kwargs(now=1))          # stale True observed
        ctrl.tick(**make_ready_kwargs(now=2, stale=False,
                                      work_signal=rl.WORK))
        self.assertFalse(ctrl.work_seen)

    def test_false_without_a_true_edge_preserves_the_latch(self):
        # Throttle skew: work lands while the cached verdict is still False
        # (no True -> False edge) — the latch must survive, or a sub-tick
        # episode under a lagging cache could never fire.
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=False)
        ctrl.tick(**make_ready_kwargs(now=1, stale=False))
        ctrl.tick(**make_ready_kwargs(now=2, stale=False,
                                      work_signal=rl.WORK))
        self.assertTrue(ctrl.work_seen)
        ctrl.tick(**make_ready_kwargs(now=3))  # stale flips True
        ctrl.tick(**make_ready_kwargs(now=4))
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=5)),
                         rl.ACTION_FIRE)

    def test_pending_arm_manual_refetch_consumes_the_latch(self):
        # Review round 4 reproduction: arm into pending staleness, the
        # shadow manually refetches before the first tick (stale=False) —
        # the arm-time True observation must seed the edge so the
        # already-reviewed latch is consumed; selection-only churn after
        # must never fire.
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        ctrl.tick(**make_ready_kwargs(now=1, stale=False))
        self.assertFalse(ctrl.work_seen)
        for i in range(10):
            self.assertEqual(
                ctrl.tick(**make_ready_kwargs(
                    now=2 + i, work_signal=rl.SELECTION_ONLY)),
                rl.ACTION_NONE, i)

    def test_prev_stale_never_crosses_lifecycles(self):
        # Review round 3: a stale prior lifecycle must not seed the edge —
        # after disarm + fresh arm, a first tick carrying BOTH work and
        # stale=False must keep the latch open (no inherited True->False).
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        ctrl.tick(**make_ready_kwargs(now=1))  # observes stale True
        ctrl.disarm()
        ctrl.arm(pending_work=False)
        ctrl.tick(**make_ready_kwargs(now=2, stale=False,
                                      work_signal=rl.WORK))
        self.assertTrue(ctrl.work_seen)

    def test_work_observed_during_modal_still_counts(self):
        ctrl = self._fired()
        base = 1002.0 + rl.COOLDOWN_SECONDS
        ctrl.tick(**make_ready_kwargs(now=base, modal_open=True,
                                      work_signal=rl.WORK))
        ctrl.tick(**make_ready_kwargs(now=base + 1))
        ctrl.tick(**make_ready_kwargs(now=base + 2))
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=base + 3)),
                         rl.ACTION_FIRE)


class ShadowPromptReadyTests(unittest.TestCase):
    def test_at_rest_with_dim_hint_is_ready(self):
        self.assertIs(
            rl.shadow_prompt_ready(fx.CLAUDE_AT_REST_RAW, "claude", True),
            True)

    def test_typed_composer_text_is_not_ready(self):
        self.assertIsNot(
            rl.shadow_prompt_ready(fx.CLAUDE_TYPED_RAW, "claude", True),
            True)

    def test_streaming_is_not_ready_even_if_hash_stable(self):
        # Streaming shows a BARE composer (measured), so the positive check
        # alone would pass — the spinner negative must refuse it.
        self.assertIsNot(
            rl.shadow_prompt_ready(fx.CLAUDE_STREAMING_RAW, "claude", True),
            True)

    def test_dialog_is_not_ready(self):
        self.assertIsNot(
            rl.shadow_prompt_ready(fx.CLAUDE_DIALOG_RAW, "claude", True),
            True)

    def test_hash_instability_blocks_a_ready_composer(self):
        self.assertIs(
            rl.shadow_prompt_ready(fx.CLAUDE_AT_REST_RAW, "claude", False),
            False)

    def test_failed_capture_and_unknown_agent_are_indeterminate(self):
        # Retargeted again in t1520: `opencode` HAS a detector now too, so no
        # member of agent_keys.AGENT_KEYS is undetected any more. The
        # unknown-agent case is therefore carried by keys that are not agents
        # at all -- with a premise assertion, so it cannot quietly go vacuous
        # if one of them is ever wired up.
        self.assertNotIn("gemini", rl.SHADOW_READY_DETECTORS)
        self.assertIsNone(rl.shadow_prompt_ready(None, "claude", True))
        self.assertIsNone(
            rl.shadow_prompt_ready(fx.CLAUDE_AT_REST_RAW, "gemini", True))
        self.assertIsNone(
            rl.shadow_prompt_ready(fx.CLAUDE_AT_REST_RAW, "", True))
        self.assertIsNone(rl.shadow_prompt_ready("", "claude", True))


class CodexShadowReadinessTests(unittest.TestCase):
    """Codex shadow readiness (t1509), pinned against live 0.146.0 captures."""

    def test_at_rest_with_dim_hint_is_ready(self):
        self.assertIs(
            rl.shadow_prompt_ready(fx.CODEX_AT_REST_RAW, "codex", True), True)

    def test_typed_working_and_every_dialog_are_not_ready(self):
        for name in ("CODEX_TYPED_RAW", "CODEX_WORKING_RAW",
                     "CODEX_PERMISSION_RAW", "CODEX_QUESTION_RAW",
                     "CODEX_UPDATE_PROMPT_RAW"):
            self.assertIsNot(
                rl.shadow_prompt_ready(getattr(fx, name), "codex", True),
                True, name)

    def test_hash_instability_blocks_a_ready_composer(self):
        self.assertIs(
            rl.shadow_prompt_ready(fx.CODEX_AT_REST_RAW, "codex", False),
            False)

    def test_failed_capture_is_indeterminate(self):
        self.assertIsNone(rl.shadow_prompt_ready(None, "codex", True))
        self.assertIsNone(rl.shadow_prompt_ready("", "codex", True))

    def test_state_verdicts_per_fixture(self):
        expected = {
            "CODEX_AT_REST_RAW": rl.SHADOW_READY,
            "CODEX_TYPED_RAW": rl.SHADOW_BUSY,
            "CODEX_WORKING_RAW": rl.SHADOW_WORKING,
            "CODEX_PERMISSION_RAW": rl.SHADOW_DIALOG,
            "CODEX_QUESTION_RAW": rl.SHADOW_DIALOG,
            "CODEX_UPDATE_PROMPT_RAW": rl.SHADOW_DIALOG,
        }
        for name, want in expected.items():
            self.assertEqual(rl._codex_state(getattr(fx, name)), want, name)

    def test_the_unpatterned_update_prompt_is_a_dialog_not_typed_text(self):
        """The assertion that pins the STRUCTURAL arming rule.

        No codex prompt pattern matches the startup update prompt, and its
        option row is rendered with the composer glyph followed by visible
        text — so a detector that classified it from the composer scan alone
        would call it SHADOW_BUSY. The caller's settle latch arms on anything
        that is not READY/WORKING either way, but the verdict must be honest
        about WHY, because a BUSY verdict would mean the loop is relying on
        pattern coverage it does not have here.
        """
        raw = fx.CODEX_UPDATE_PROMPT_RAW
        plain = rl.strip_ansi(raw)
        # Negative control on the premise: no pattern matches this capture.
        for pattern in rl.PROMPT_PATTERNS_BY_AGENT.get("codex", []):
            self.assertIsNone(pattern.regex.search(plain), pattern.name)
        self.assertEqual(rl._codex_state(raw), rl.SHADOW_DIALOG)


class CodexIsolatedPositiveHalfTests(unittest.TestCase):
    """The task's explicit safety question, as an executable assertion.

    Can a Codex pane parked at a dialog satisfy the POSITIVE empty-composer
    half? Run the detector with the codex pattern list emptied — if a dialog
    still reads as not-ready, the exclusion is structural (the dialog replaces
    the composer) rather than an artifact of pattern coverage.
    """

    def setUp(self):
        self._saved = rl.PROMPT_PATTERNS_BY_AGENT.get("codex", [])
        rl.PROMPT_PATTERNS_BY_AGENT["codex"] = []

    def tearDown(self):
        rl.PROMPT_PATTERNS_BY_AGENT["codex"] = self._saved

    def test_dialogs_are_excluded_with_the_pattern_list_disabled(self):
        for name in ("CODEX_PERMISSION_RAW", "CODEX_QUESTION_RAW",
                     "CODEX_UPDATE_PROMPT_RAW"):
            self.assertIsNot(rl._codex_ready(getattr(fx, name)), True, name)

    def test_the_disabling_is_real(self):
        """Negative control on the harness itself: with the patterns gone the
        WORKING fixture must lose nothing (it never depended on them), while
        at-rest must still be ready — proving setUp did not simply break the
        detector into answering False for everything."""
        self.assertEqual(rl.PROMPT_PATTERNS_BY_AGENT["codex"], [])
        self.assertIs(rl._codex_ready(fx.CODEX_AT_REST_RAW), True)
        self.assertIs(rl._codex_ready(fx.CODEX_WORKING_RAW), False)


class CodexDetectorNegativeControlTests(unittest.TestCase):
    """One mutation each, so a passing suite cannot be vacuous."""

    def test_claudes_nbsp_composer_regex_would_break_codex_at_rest(self):
        """Codex's glyph is followed by a PLAIN space, not an NBSP. Swapping in
        Claude's composer regex must stop at-rest reading as ready — pinning
        that the plain-space form is load-bearing and not incidental."""
        state = rl._composer_state(
            fx.CODEX_AT_REST_RAW, agent="codex",
            composer_re=rl._CLAUDE_COMPOSER_RE,
            working_re=rl._CODEX_WORKING_RE, pad=" ",
            option_row_re=rl._CODEX_OPTION_ROW_RE)
        self.assertNotEqual(state, rl.SHADOW_READY)

    def test_without_the_working_regex_streaming_reads_as_ready(self):
        """Codex renders the IDENTICAL empty dim-hint composer while working,
        so the working regex is the only thing excluding the streaming state.
        Remove it and the fixture must flip to ready."""
        never = re.compile(r"(?!x)x")
        self.assertEqual(
            rl._composer_state(fx.CODEX_WORKING_RAW, agent="codex",
                               composer_re=rl._CODEX_COMPOSER_RE,
                               working_re=never, pad=" ",
                               option_row_re=rl._CODEX_OPTION_ROW_RE),
            rl.SHADOW_READY)
        # ... and with it, it does not.
        self.assertEqual(rl._codex_state(fx.CODEX_WORKING_RAW),
                         rl.SHADOW_WORKING)

    def test_an_unanchored_esc_to_interrupt_would_false_positive_on_boot(self):
        """Measured live: an unanchored `esc to interrupt` alternation matches
        Codex's boot/tip text. A false WORKING there would CLEAR the caller's
        settle latch, so this pins the anchored form."""
        unanchored = re.compile(
            r"(?m)^\s*\u2022\s+(?:Working|Running)\b|esc to interrupt")
        self.assertIsNone(
            rl._CODEX_WORKING_RE.search(rl.strip_ansi(fx.CODEX_AT_REST_RAW)))
        boot_tail = rl.strip_ansi(fx.CODEX_AT_REST_RAW) + "\n  esc to interrupt\n"
        self.assertIsNotNone(unanchored.search(boot_tail))
        self.assertIsNone(rl._CODEX_WORKING_RE.search(boot_tail))

    def test_dialog_outranks_working_when_both_are_visible(self):
        """Codex keeps its `Running <cmd>` line on screen WHILE parked at a
        permission dialog, so a working-first order would report WORKING for a
        pane that is still waiting on the user — clearing the caller's settle
        latch at exactly the wrong moment. Pins the order against that
        inversion; the other permission fixture's 15-line window excludes the
        status line, which makes the ordering invisible there.
        """
        raw = fx.CODEX_PERMISSION_WITH_RUNNING_RAW
        plain = rl.strip_ansi(raw)
        # Premise: BOTH signals really are present in this window.
        self.assertIsNotNone(rl._CODEX_WORKING_RE.search(plain))
        self.assertTrue(any(p.regex.search(plain)
                            for p in rl.PROMPT_PATTERNS_BY_AGENT["codex"]))
        # Verdict: dialog wins.
        self.assertEqual(rl._codex_state(raw), rl.SHADOW_DIALOG)
        self.assertIs(rl.shadow_prompt_ready(raw, "codex", True), False)

    def test_claude_readiness_is_unchanged_by_the_refactor(self):
        """Characterization guard: `_claude_ready` is now derived from
        `_claude_state`, so every Claude fixture must keep its old verdict."""
        self.assertIs(
            rl.shadow_prompt_ready(fx.CLAUDE_AT_REST_RAW, "claude", True), True)
        for name in ("CLAUDE_TYPED_RAW", "CLAUDE_STREAMING_RAW",
                     "CLAUDE_DIALOG_RAW"):
            self.assertIs(
                rl.shadow_prompt_ready(getattr(fx, name), "claude", True),
                False, name)

    def test_claude_state_verdicts_per_fixture(self):
        """Claude's verdict table, mirroring the Codex and OpenCode ones.

        The characterization guard above only pins "not ready", which was
        enough while readiness was the sole consumer. The t1525 delivery reads
        the SPECIFIC verdict — it authorises an Enter on `SHADOW_BUSY` alone
        and treats `SHADOW_DIALOG` as unverifiable — so the consumer's guard
        has to be pinned wherever the producer is, for every agent.
        """
        expected = {
            "CLAUDE_AT_REST_RAW": rl.SHADOW_READY,
            "CLAUDE_TYPED_RAW": rl.SHADOW_BUSY,
            "CLAUDE_STREAMING_RAW": rl.SHADOW_WORKING,
            "CLAUDE_DIALOG_RAW": rl.SHADOW_DIALOG,
        }
        for name, want in expected.items():
            self.assertEqual(rl._claude_state(getattr(fx, name)), want, name)

    def test_every_shadow_agent_reads_typed_text_as_busy(self):
        """The delivery's authorising verdict is agent-invariant.

        `_submit_shadow_prompt` sends its Enter only when the post-write
        readback is `SHADOW_BUSY`. If any shadow agent classified its own
        typed composer as something else, the loop would veto every delivery
        into that agent — silently, and only in production.
        """
        typed = {"claude": fx.CLAUDE_TYPED_RAW,
                 "codex": fx.CODEX_TYPED_RAW,
                 "opencode": fx.OPENCODE_TYPED_RAW}
        self.assertEqual(sorted(typed), sorted(rl.SHADOW_STATE_DETECTORS),
                         "an agent gained a detector but no typed fixture here")
        for agent, raw in typed.items():
            self.assertEqual(rl.shadow_state(raw, agent), rl.SHADOW_BUSY, agent)

    def test_the_two_dispatch_tables_cannot_drift(self):
        self.assertEqual(sorted(rl.SHADOW_READY_DETECTORS),
                         sorted(rl.SHADOW_STATE_DETECTORS))


class ComposerDrainConstantTests(unittest.TestCase):
    """The drain is the actual t1525 repair; these keep it from rotting to 0."""

    def test_drain_clears_the_measured_floor(self):
        """Pre-phase sweep (2026-08-16): at d=0 codex-cli 0.146.0 swallowed the
        Enter in 10/10 repetitions — the prompt was never submitted — while
        d=0.25 submitted 10/10. The shipped value keeps margin over that floor.

        This assertion is the only thing standing between the repo and a silent
        regression to the t1525 failure: with the drain seam stubbed out in the
        app tests, `COMPOSER_DRAIN_SECONDS = 0.0` fails nothing else.
        """
        self.assertGreaterEqual(rl.COMPOSER_DRAIN_SECONDS, 0.25)

    def test_the_retry_budget_is_bounded_and_non_zero(self):
        self.assertGreaterEqual(rl.SHADOW_SUBMIT_RETRIES, 1)
        self.assertLessEqual(rl.SHADOW_SUBMIT_RETRIES, 3)


class OpenCodeShadowReadinessTests(unittest.TestCase):
    """OpenCode shadow readiness (t1520), pinned against live 1.18.18 captures."""

    def test_at_rest_after_a_turn_is_ready(self):
        """The DURABLE at-rest case, listed first on purpose: after one turn
        the placeholder hint is gone entirely, so this reaches READY with no
        hint machinery involved at all."""
        self.assertIs(
            rl.shadow_prompt_ready(fx.OPENCODE_AT_REST_AFTER_TURN_RAW,
                                   "opencode", True), True)

    def test_at_rest_on_a_fresh_session_with_the_gray_hint_is_ready(self):
        self.assertIs(
            rl.shadow_prompt_ready(fx.OPENCODE_AT_REST_FRESH_RAW,
                                   "opencode", True), True)

    def test_typed_working_and_every_dialog_are_not_ready(self):
        for name in ("OPENCODE_TYPED_RAW", "OPENCODE_WORKING_RAW",
                     "OPENCODE_PERMISSION_RAW", "OPENCODE_PALETTE_RAW",
                     "OPENCODE_WORKING_NO_FOOTER_ROOM_RAW"):
            self.assertIsNot(
                rl.shadow_prompt_ready(getattr(fx, name), "opencode", True),
                True, name)

    def test_hash_instability_blocks_a_ready_composer(self):
        self.assertIs(
            rl.shadow_prompt_ready(fx.OPENCODE_AT_REST_AFTER_TURN_RAW,
                                   "opencode", False), False)

    def test_failed_capture_is_indeterminate(self):
        self.assertIsNone(rl.shadow_prompt_ready(None, "opencode", True))
        self.assertIsNone(rl.shadow_prompt_ready("", "opencode", True))

    def test_state_verdicts_per_fixture(self):
        expected = {
            "OPENCODE_AT_REST_FRESH_RAW": rl.SHADOW_READY,
            "OPENCODE_AT_REST_AFTER_TURN_RAW": rl.SHADOW_READY,
            "OPENCODE_TYPED_RAW": rl.SHADOW_BUSY,
            "OPENCODE_WORKING_RAW": rl.SHADOW_WORKING,
            "OPENCODE_PERMISSION_RAW": rl.SHADOW_DIALOG,
            "OPENCODE_PALETTE_RAW": rl.SHADOW_DIALOG,
            # No room below the border => the footer could not have been shown,
            # so a would-be READY is unknowable rather than trusted.
            "OPENCODE_WORKING_NO_FOOTER_ROOM_RAW": rl.SHADOW_UNKNOWN,
        }
        for name, want in expected.items():
            self.assertEqual(rl._opencode_state(getattr(fx, name)), want, name)

    def test_readiness_does_not_depend_on_the_placeholder_hint(self):
        """The durability finding as an executable assertion.

        The gray hint is present on a fresh session and GONE after the first
        turn (measured live). A detector that anchored readiness on the hint
        would therefore work exactly once per session; both fixtures must agree.
        """
        plain_after = rl.strip_ansi(fx.OPENCODE_AT_REST_AFTER_TURN_RAW)
        self.assertNotIn("Ask anything", plain_after)   # premise: hint is gone
        self.assertIn("Ask anything",
                      rl.strip_ansi(fx.OPENCODE_AT_REST_FRESH_RAW))
        self.assertEqual(rl._opencode_state(fx.OPENCODE_AT_REST_AFTER_TURN_RAW),
                         rl._opencode_state(fx.OPENCODE_AT_REST_FRESH_RAW))

    def test_opencode_is_in_both_dispatch_tables(self):
        """`test_the_two_dispatch_tables_cannot_drift` pins PARITY, not
        MEMBERSHIP -- both tables could lose `opencode` together and still be
        equal."""
        self.assertIn("opencode", rl.SHADOW_READY_DETECTORS)
        self.assertIn("opencode", rl.SHADOW_STATE_DETECTORS)


class OpenCodeIsolatedPositiveHalfTests(unittest.TestCase):
    """Which exclusions are STRUCTURAL, and which rest on pattern coverage.

    Run the detector with the opencode pattern list emptied. The permission
    dialog must still be not-ready (it REPLACES the composer box). The palette
    must NOT be -- it is an overlay that leaves the box intact -- and asserting
    that honestly is what stops a reader generalising the dialog's structural
    exclusion to every OpenCode interaction.
    """

    def setUp(self):
        self._saved = rl.PROMPT_PATTERNS_BY_AGENT.get("opencode", [])
        rl.PROMPT_PATTERNS_BY_AGENT["opencode"] = []

    def tearDown(self):
        rl.PROMPT_PATTERNS_BY_AGENT["opencode"] = self._saved

    def test_the_permission_dialog_is_excluded_with_the_pattern_list_disabled(self):
        self.assertIsNot(rl._opencode_ready(fx.OPENCODE_PERMISSION_RAW), True)

    def test_the_palette_is_excluded_only_by_its_pattern(self):
        """Deliberately asserts the LIMIT of the structural half.

        The command palette renders as an overlay above an intact composer box,
        so with the patterns gone it reads ready. That is why
        `opencode_palette` exists in prompt_patterns.py, and why the structural
        argument must not be over-claimed.
        """
        self.assertIs(rl._opencode_ready(fx.OPENCODE_PALETTE_RAW), True)
        rl.PROMPT_PATTERNS_BY_AGENT["opencode"] = self._saved
        self.assertIs(rl._opencode_ready(fx.OPENCODE_PALETTE_RAW), False)

    def test_the_disabling_is_real(self):
        """Negative control on the harness itself: with the patterns gone
        at-rest must still be ready and working must still not be, proving
        setUp did not simply break the detector into answering False for
        everything."""
        self.assertEqual(rl.PROMPT_PATTERNS_BY_AGENT["opencode"], [])
        self.assertIs(rl._opencode_ready(fx.OPENCODE_AT_REST_AFTER_TURN_RAW),
                      True)
        self.assertIs(rl._opencode_ready(fx.OPENCODE_WORKING_RAW), False)

    def test_the_permission_dialog_really_has_no_composer_box(self):
        """Premise assertion, by name.

        The structural exclusion rests entirely on the dialog rendering no
        border and no status row. The day OpenCode draws the box behind the
        dialog, this fails LOUDLY instead of the guard silently degrading into
        pattern-only exclusion.
        """
        lines = rl.strip_ansi(fx.OPENCODE_PERMISSION_RAW).splitlines()
        self.assertFalse(any(rl._OPENCODE_BOX_BOTTOM_RE.match(l.rstrip())
                             for l in lines), "dialog grew a box border")
        self.assertFalse(any(rl._OPENCODE_STATUS_ROW_RE.match(l.rstrip())
                             for l in lines), "dialog grew a status row")
        # ...and it really does contain the blank gutter rows that make the
        # naive rule dangerous.
        self.assertTrue(any(l.strip() == "┃" for l in lines))


class OpenCodeDetectorNegativeControlTests(unittest.TestCase):
    """One mutation each, so a passing suite cannot be vacuous."""

    def test_a_blank_gutter_row_rule_false_positives_on_the_permission_dialog(self):
        """The headline control. The permission dialog is ALSO a `┃`-gutter box
        containing blank rows, so a naive "a blank gutter row exists" rule
        cannot tell it from an idle composer. Demonstrated, not asserted."""
        naive = re.compile("(?m)^\\s*┃\\s*$")
        for name in ("OPENCODE_PERMISSION_RAW",
                     "OPENCODE_AT_REST_AFTER_TURN_RAW"):
            self.assertIsNotNone(
                naive.search(rl.strip_ansi(getattr(fx, name))),
                f"{name}: the naive blank-gutter rule matches this too")
        # The shipped classifier tells them apart; the anchor is what does it.
        self.assertEqual(rl._opencode_state(fx.OPENCODE_PERMISSION_RAW),
                         rl.SHADOW_DIALOG)
        self.assertEqual(rl._opencode_state(fx.OPENCODE_AT_REST_AFTER_TURN_RAW),
                         rl.SHADOW_READY)

    def test_the_status_row_anchor_is_load_bearing(self):
        """Drop the status-row corroboration and an idle box stops being ready.

        The border alone decides `is a composer box present`; the status row is
        what stops a stray border plus any blank `┃` rows from being ACCEPTED as
        one. Removing it must change the verdict of a genuinely idle pane.

        Note the permission dialog deliberately gets no equivalent
        single-mutation control: its exclusion is over-determined (the
        `opencode_permission` pattern, the missing border, the missing status
        row and the window guard each refuse it independently), so no one
        mutation flips it to ready. That it carries NEITHER anchor is asserted
        directly in `test_the_permission_dialog_really_has_no_composer_box`.
        """
        never = re.compile(r"(?!x)x")
        self.assertEqual(
            rl._ordered_state(fx.OPENCODE_AT_REST_AFTER_TURN_RAW,
                              agent="opencode",
                              positive=functools.partial(
                                  rl._opencode_box_state, status_re=never),
                              working_re=rl._OPENCODE_WORKING_RE),
            rl.SHADOW_DIALOG)
        # ... and with it, the same capture is ready.
        self.assertEqual(rl._opencode_state(fx.OPENCODE_AT_REST_AFTER_TURN_RAW),
                         rl.SHADOW_READY)

    def test_without_the_working_footer_regex_a_working_pane_reads_as_ready(self):
        """OpenCode renders the IDENTICAL empty composer box while working --
        at-rest and working are indistinguishable INSIDE the box -- so the
        footer regex is the only thing excluding the working state."""
        never = re.compile(r"(?!x)x")
        self.assertEqual(
            rl._ordered_state(fx.OPENCODE_WORKING_RAW, agent="opencode",
                              positive=rl._opencode_box_state,
                              working_re=never),
            rl.SHADOW_READY)
        # ... and with it, it does not.
        self.assertEqual(rl._opencode_state(fx.OPENCODE_WORKING_RAW),
                         rl.SHADOW_WORKING)

    def test_the_gray_hint_span_is_what_makes_a_fresh_session_ready(self):
        """Proves the hint is SUBTRACTED, not relied on: drop the span regex
        and the FRESH fixture flips to busy while the after-a-turn one, which
        never reaches the subtraction, stays ready."""
        never = re.compile(r"(?!x)x")
        blind = functools.partial(rl._opencode_box_state, hint_span_re=never)
        self.assertEqual(
            rl._ordered_state(fx.OPENCODE_AT_REST_FRESH_RAW, agent="opencode",
                              positive=blind,
                              working_re=rl._OPENCODE_WORKING_RE),
            rl.SHADOW_BUSY)
        self.assertEqual(
            rl._ordered_state(fx.OPENCODE_AT_REST_AFTER_TURN_RAW,
                              agent="opencode", positive=blind,
                              working_re=rl._OPENCODE_WORKING_RE),
            rl.SHADOW_READY)

    def test_dim_span_regex_does_not_transfer_to_opencode(self):
        """Why a sibling classifier exists at all: OpenCode carries NO SGR-dim
        in its composer, so the Claude/Codex discriminator finds nothing."""
        self.assertIsNone(
            rl._DIM_SPAN_RE.search(fx.OPENCODE_AT_REST_FRESH_RAW))
        self.assertIsNotNone(
            rl._OPENCODE_HINT_SPAN_RE.search(fx.OPENCODE_AT_REST_FRESH_RAW))

    def test_a_working_pane_whose_footer_had_no_room_is_not_ready(self):
        """The fail-dangerous case, reproduced live at pane height 6 and
        verified against the opencode process tree's CPU time.

        No room below the border => no footer => an empty box reading `ready`,
        AND a byte-identical capture, so the hash-stability brake fails at the
        same moment. Without the window guard this returns READY/True, which is
        the inject-into-a-working-shadow failure.
        """
        raw = fx.OPENCODE_WORKING_NO_FOOTER_ROOM_RAW
        plain = rl.strip_ansi(raw)
        # Premise: the footer really is unobservable in this capture...
        self.assertIsNone(rl._OPENCODE_WORKING_RE.search(plain))
        # ...and the box IS present and empty, so the positive half would pass.
        lines = plain.splitlines()
        border = next(i for i in range(len(lines) - 1, -1, -1)
                      if rl._OPENCODE_BOX_BOTTOM_RE.match(lines[i].rstrip()))
        self.assertEqual(len(lines) - 1 - border, 0)
        # Verdict: unknowable, never ready.
        self.assertEqual(rl._opencode_state(raw), rl.SHADOW_UNKNOWN)
        self.assertIsNone(rl.shadow_prompt_ready(raw, "opencode", True))

    def test_ordinary_idle_geometry_is_not_swallowed_by_the_window_guard(self):
        """The guard's OTHER direction. A fail-closed guard that fired on
        normal geometry would make every ready pane UNKNOWN and silently stop
        the loop ever firing for OpenCode -- no error, no banner."""
        for name in ("OPENCODE_AT_REST_FRESH_RAW",
                     "OPENCODE_AT_REST_AFTER_TURN_RAW"):
            raw = getattr(fx, name)
            lines = rl.strip_ansi(raw).splitlines()
            border = next(i for i in range(len(lines) - 1, -1, -1)
                          if rl._OPENCODE_BOX_BOTTOM_RE.match(lines[i].rstrip()))
            self.assertGreaterEqual(
                len(lines) - 1 - border,
                rl._OPENCODE_MIN_LINES_BELOW_BORDER, name)
            self.assertEqual(rl._opencode_state(raw), rl.SHADOW_READY, name)

    def test_the_palette_is_excluded_at_the_minimum_ready_eligible_geometry(self):
        """Review follow-up: the palette anchor is the header row, which at
        full size renders ~21 rows above the bottom. If a pane were short
        enough to CLIP the header while leaving the composer intact, the
        negative half would miss an awaiting-input overlay and an injected
        Enter would run the selected command.

        Measured across every ready-eligible geometry (heights 7-30, widths
        40-100): it cannot happen, for two independent reasons, and both are
        asserted here on the tightest capture that still permits READY.

        1. OpenCode draws the palette CENTRED OVER the composer box at compact
           sizes rather than above it, so the header cannot scroll off -- it
           lands inside the box region. This is the assertion that carries the
           test: drop `opencode_palette` and it fails.
        2. Overwriting the box also disrupts it -- the status row loses a
           `·`-separated field and a content row gains the overlay's text -- so
           the structural half refuses too, with the pattern list disabled.

        Like the permission dialog, the compact palette is therefore
        OVER-DETERMINED: no single mutation flips it to ready, and the isolated
        assertion below is a belt-and-braces statement rather than a control.
        The geometry premise and the header-visibility assertion are the parts
        that discriminate.
        """
        raw = fx.OPENCODE_PALETTE_COMPACT_RAW
        plain = rl.strip_ansi(raw)
        lines = plain.splitlines()

        # Premise: this really is at the minimum geometry the window guard
        # still allows a READY at -- exactly one line below the border.
        border = next(i for i in range(len(lines) - 1, -1, -1)
                      if rl._OPENCODE_BOX_BOTTOM_RE.match(lines[i].rstrip()))
        self.assertEqual(len(lines) - 1 - border,
                         rl._OPENCODE_MIN_LINES_BELOW_BORDER)
        # ...and the palette really is open, with its header still visible.
        #
        # Both halves are pinned WITHOUT going through "some opencode pattern
        # matched": a future broad or overlapping pattern would satisfy that
        # even after the header had disappeared, masking the very geometry
        # contract this test exists to pin. So assert the header text directly,
        # and select `opencode_palette` BY NAME.
        self.assertIn("Commands", plain,
                      "palette header clipped at the minimum geometry")
        palette = next((p for p in rl.PROMPT_PATTERNS_BY_AGENT["opencode"]
                        if p.name == "opencode_palette"), None)
        self.assertIsNotNone(palette, "opencode_palette pattern is gone")
        self.assertIsNotNone(
            palette.regex.search(plain),
            "opencode_palette no longer matches at the minimum geometry")

        self.assertEqual(rl._opencode_state(raw), rl.SHADOW_DIALOG)
        self.assertIs(rl.shadow_prompt_ready(raw, "opencode", True), False)

        # Reason 2, isolated: still refused with the patterns gone.
        saved = rl.PROMPT_PATTERNS_BY_AGENT["opencode"]
        rl.PROMPT_PATTERNS_BY_AGENT["opencode"] = []
        try:
            self.assertIsNot(rl._opencode_ready(raw), True)
        finally:
            rl.PROMPT_PATTERNS_BY_AGENT["opencode"] = saved

    def test_a_compact_idle_pane_is_still_ready(self):
        """The availability half at the minimum geometry (40x7 -- narrowest and
        shortest that still permits READY). Without this, the test above could
        be satisfied by a detector that simply never says ready when the pane
        is small, which would silently stop the loop firing for split shadows.
        """
        raw = fx.OPENCODE_AT_REST_COMPACT_RAW
        self.assertEqual(rl._opencode_state(raw), rl.SHADOW_READY)
        self.assertIs(rl.shadow_prompt_ready(raw, "opencode", True), True)

    def test_a_near_miss_separator_row_does_not_satisfy_the_status_row_rule(self):
        """The status-row grammar control, on a REAL captured row.

        The transcript renders `▣  Build · GPT-5.4` -- same mode word, same
        separator, but no gutter and one field fewer. A permissive rule would
        accept it and let an unrelated row corroborate a stray border.
        """
        near = [l for l in rl.strip_ansi(fx.OPENCODE_PERMISSION_RAW).splitlines()
                if "·" in l and "┃" not in l]
        self.assertTrue(near, "expected a real near-miss row in the fixture")
        for line in near:
            self.assertIsNone(rl._OPENCODE_STATUS_ROW_RE.match(line.rstrip()),
                              f"near miss accepted: {line!r}")
        # The genuine status row is accepted.
        real = [l for l in
                rl.strip_ansi(fx.OPENCODE_AT_REST_AFTER_TURN_RAW).splitlines()
                if rl._OPENCODE_STATUS_ROW_RE.match(l.rstrip())]
        self.assertEqual(len(real), 1, "expected exactly one status row")

    def test_claude_and_codex_are_unchanged_by_the_ordering_extraction(self):
        """Characterization guard on the `_ordered_state` extraction: every
        pre-existing fixture keeps the verdict recorded before the refactor."""
        expected = {
            ("CLAUDE_AT_REST_RAW", "claude"): rl.SHADOW_READY,
            ("CLAUDE_TYPED_RAW", "claude"): rl.SHADOW_BUSY,
            ("CLAUDE_STREAMING_RAW", "claude"): rl.SHADOW_WORKING,
            ("CLAUDE_DIALOG_RAW", "claude"): rl.SHADOW_DIALOG,
            ("CODEX_AT_REST_RAW", "codex"): rl.SHADOW_READY,
            ("CODEX_TYPED_RAW", "codex"): rl.SHADOW_BUSY,
            ("CODEX_WORKING_RAW", "codex"): rl.SHADOW_WORKING,
            ("CODEX_PERMISSION_RAW", "codex"): rl.SHADOW_DIALOG,
            ("CODEX_QUESTION_RAW", "codex"): rl.SHADOW_DIALOG,
            ("CODEX_UPDATE_PROMPT_RAW", "codex"): rl.SHADOW_DIALOG,
            ("CODEX_PERMISSION_WITH_RUNNING_RAW", "codex"): rl.SHADOW_DIALOG,
        }
        for (name, agent), want in expected.items():
            self.assertEqual(rl.shadow_state(getattr(fx, name), agent), want,
                             name)


class ClassifyFollowedChangeTests(unittest.TestCase):
    KIND_Q = "claude_askuserquestion"
    KIND_P = "claude_plan_approval"

    def test_no_baseline_is_unknown(self):
        self.assertEqual(
            rl.classify_followed_change(None, "", fx.ASKUSER_SEL1,
                                        self.KIND_Q, True, "claude"),
            rl.UNKNOWN)

    def test_identical_content_is_none(self):
        self.assertEqual(
            rl.classify_followed_change(fx.ASKUSER_SEL1, self.KIND_Q,
                                        fx.ASKUSER_SEL1, self.KIND_Q,
                                        True, "claude"),
            rl.NO_CHANGE)

    def test_change_while_not_awaiting_is_work(self):
        self.assertEqual(
            rl.classify_followed_change("old output", "", "new output", "",
                                        False, "claude"),
            rl.WORK)

    def test_kind_change_is_work(self):
        self.assertEqual(
            rl.classify_followed_change(fx.ASKUSER_SEL1, self.KIND_Q,
                                        fx.PLAN_SEL1, self.KIND_P,
                                        True, "claude"),
            rl.WORK)

    def test_askuser_selection_navigation_is_selection_only(self):
        self.assertEqual(
            rl.classify_followed_change(fx.ASKUSER_SEL1, self.KIND_Q,
                                        fx.ASKUSER_SEL2, self.KIND_Q,
                                        True, "claude"),
            rl.SELECTION_ONLY)

    def test_plan_dialog_selection_navigation_is_selection_only(self):
        # The native plan-approval dialog has NO question chip — this is the
        # boundary-pattern path (review hardening 7), on real captures.
        self.assertEqual(
            rl.classify_followed_change(fx.PLAN_SEL1, self.KIND_P,
                                        fx.PLAN_SEL2, self.KIND_P,
                                        True, "claude"),
            rl.SELECTION_ONLY)

    def test_revised_plan_dialog_is_work(self):
        self.assertEqual(
            rl.classify_followed_change(fx.PLAN_SEL2, self.KIND_P,
                                        fx.PLAN_REVISED, self.KIND_P,
                                        True, "claude"),
            rl.WORK)

    def test_history_growth_is_work_even_with_identical_tails(self):
        self.assertEqual(
            rl.classify_followed_change(fx.PLAN_SEL1, self.KIND_P,
                                        fx.PLAN_SEL1, self.KIND_P,
                                        True, "claude", 28, 61),
            rl.WORK)

    def test_history_shrink_or_missing_contributes_nothing(self):
        self.assertEqual(
            rl.classify_followed_change(fx.PLAN_SEL1, self.KIND_P,
                                        fx.PLAN_SEL1, self.KIND_P,
                                        True, "claude", 61, 28),
            rl.NO_CHANGE)
        self.assertEqual(
            rl.classify_followed_change(fx.PLAN_SEL1, self.KIND_P,
                                        fx.PLAN_SEL1, self.KIND_P,
                                        True, "claude", None, 61),
            rl.NO_CHANGE)

    def test_resize_suppresses_both_evidence_channels(self):
        # Review round 2: a plain resize reflows content AND re-buckets
        # history (measured 471 -> 491 on 120x30 -> 50x10 with no output).
        # Neither channel may read it as work.
        self.assertEqual(
            rl.classify_followed_change(fx.PLAN_SEL1, self.KIND_P,
                                        fx.PLAN_REVISED, self.KIND_P,
                                        True, "claude", 471, 491,
                                        (120, 30), (50, 10)),
            rl.UNKNOWN)

    def test_constant_geometry_keeps_the_history_rule(self):
        # Positive control for the resize guard: same delta, same geometry.
        self.assertEqual(
            rl.classify_followed_change(fx.PLAN_SEL1, self.KIND_P,
                                        fx.PLAN_SEL1, self.KIND_P,
                                        True, "claude", 471, 491,
                                        (120, 30), (120, 30)),
            rl.WORK)

    def test_unknown_geometry_is_backcompat(self):
        self.assertEqual(
            rl.classify_followed_change(fx.PLAN_SEL1, self.KIND_P,
                                        fx.PLAN_SEL1, self.KIND_P,
                                        True, "claude", 28, 61,
                                        None, None),
            rl.WORK)

    def test_awaiting_change_with_unanchorable_kind_is_unknown(self):
        # A prompt kind with no chip and no boundary strategy: conservative.
        self.assertEqual(
            rl.classify_followed_change("a", "claude_trust_folder",
                                        "b", "claude_trust_folder",
                                        True, "claude"),
            rl.UNKNOWN)

    def test_chip_kind_with_unlocatable_chip_is_unknown(self):
        self.assertEqual(
            rl.classify_followed_change("no chip here", self.KIND_Q,
                                        "still no chip", self.KIND_Q,
                                        True, "claude"),
            rl.UNKNOWN)


class ReviewLoopAgentSupportTests(unittest.TestCase):
    """The arming predicate is SEPARATE from `live_tiers_available` (t1467).

    That separation is invisible to inspection once both look like per-agent
    predicates, so it is asserted directly. It is still real after t1518, even
    though all three shipped agents now satisfy both: an agent wired into
    AGENT_KEYS ahead of its own live boundary evidence satisfies the first and
    must not satisfy the second.
    """

    def test_truth_table(self):
        """Every agent armable today earned it with its own live evidence."""
        for agent in ("claude", "codex", "opencode"):
            self.assertTrue(rl.review_loop_agent_supported(agent), agent)

    def test_unknown_and_empty_are_not_supported(self):
        for agent in ("", "node", "python", "some_future_agent"):
            self.assertFalse(rl.review_loop_agent_supported(agent))

    def test_predicate_matches_its_constant(self):
        """Guards against the predicate and the constant drifting apart."""
        for agent in rl.REVIEW_LOOP_AGENTS:
            self.assertTrue(rl.review_loop_agent_supported(agent))

    def test_arming_predicate_is_not_live_tiers_available(self):
        """The two predicates agree on today's agents — assert they are not the
        SAME predicate, or the distinction quietly becomes an alias.

        A synthetic agent with a question-widget kind (hence live tiers) but no
        entry in the armable tuple must split them.
        """
        agent = "synthetic_wired_agent"
        prev = wp.QUESTION_WIDGET_KINDS.get(agent)
        wp.QUESTION_WIDGET_KINDS[agent] = ("synthetic_question",)
        try:
            self.assertTrue(wp.live_tiers_available(agent))
            self.assertFalse(
                rl.review_loop_agent_supported(agent),
                "live tiers must not confer arming — the loop injects keys")
        finally:
            if prev is None:
                wp.QUESTION_WIDGET_KINDS.pop(agent, None)
            else:
                wp.QUESTION_WIDGET_KINDS[agent] = prev


class ArmedAgentKindCoverageTests(unittest.TestCase):
    """Every awaiting-input kind an ARMED agent can report must resolve.

    A weaker "the agent has *some* strategy" guard is worthless here: Codex and
    OpenCode have satisfied the question-widget half since t1467, so such a
    guard stays green while a permission-dialog row is omitted or later
    deleted — and the loop would arm while classifying that dialog UNKNOWN,
    which is exactly the gap t1518 closed.
    """

    @staticmethod
    def _reportable_kinds(agent: str) -> set[str]:
        """The kinds production can actually report for `agent`.

        Derived from the PRODUCTION seam, never reassembled by hand.
        `TmuxMonitor` defaults its pattern list to `all_patterns()` and
        `classify_content` narrows it with `scope_patterns`, which is
        SUBTRACTIVE and deliberately retains the cross-agent `"all"` group for
        every resolved agent. A union built from `PROMPT_PATTERNS_BY_AGENT`
        alone would silently exclude that group.
        """
        return {p.name for p in pp.scope_patterns(pp.all_patterns(), agent)}

    @staticmethod
    def _resolves(agent: str, kind: str) -> bool:
        return (kind in wp.QUESTION_WIDGET_KINDS.get(agent, ())
                or rl.native_dialog_anchored(agent, kind)
                or (agent, kind) in rl.DELIBERATELY_UNANCHORED_KINDS)

    def _unresolved(self, agents=None) -> list[tuple[str, str]]:
        out = []
        for agent in (agents if agents is not None else rl.REVIEW_LOOP_AGENTS):
            kinds = self._reportable_kinds(agent)
            self.assertTrue(kinds, f"{agent} has no reportable prompt kinds")
            out += [(agent, k) for k in sorted(kinds)
                    if not self._resolves(agent, k)]
        return out

    def test_every_armed_agent_kind_resolves(self):
        self.assertEqual(
            self._unresolved(), [],
            "an armed agent's dialog would classify UNKNOWN — give it a "
            "boundary, or record it in DELIBERATELY_UNANCHORED_KINDS with a "
            "reason")

    # --- negative controls: each mutation must make the guard fail ----------

    def test_control_dropping_a_permission_row_fails_the_guard(self):
        """Mutate the shipped dict, never delete the source line: a deleted
        line fails with KeyError/NameError, which proves nothing about the
        guard."""
        key = ("codex", "codex_permission")
        removed = rl.NATIVE_DIALOG_BOUNDARIES.pop(key)
        try:
            self.assertIn(key, self._unresolved())
        finally:
            rl.NATIVE_DIALOG_BOUNDARIES[key] = removed
        self.assertEqual(self._unresolved(), [])  # restored

    def test_control_agent_without_strategies_fails_the_guard(self):
        """A newly-wired agent with patterns but no boundaries must fail.

        Asserted in BOTH scoping regimes, because they differ and only one is
        the realistic shape:

        * registered in `AGENT_KEYS` — scoping narrows to the agent's own
          group, so its single kind is the only unresolved one;
        * NOT registered — `scope_patterns` fails open to the whole flat list
          (its documented pre-t1467 behaviour), so the guard flags every kind
          the agent could report. Still a failure, and a louder one.
        """
        agent = "synthetic_unanchored_agent"
        kind = "synthetic_agent_prompt"
        pp.PROMPT_PATTERNS_BY_AGENT[agent] = [
            pp.PromptPattern(kind, re.compile("zzz"))]
        try:
            # Unregistered: fail-open flat list, so the agent's own kind is
            # present among many.
            self.assertIn((agent, kind), self._unresolved([agent]))

            # Registered: scoping narrows, and its kind is the ONLY one left.
            prev_keys = pp.AGENT_KEYS
            pp.AGENT_KEYS = prev_keys + (agent,)
            try:
                self.assertEqual(self._unresolved([agent]), [(agent, kind)])
            finally:
                pp.AGENT_KEYS = prev_keys
        finally:
            pp.PROMPT_PATTERNS_BY_AGENT.pop(agent, None)

    def test_control_generic_all_group_pattern_fails_the_guard(self):
        """Pins the `"all"`-group derivation.

        `scope_patterns` retains the `"all"` group for EVERY resolved agent, so
        a generic prompt added there becomes reportable for all of them. If the
        guard's kind set is ever narrowed back to `PROMPT_PATTERNS_BY_AGENT[
        agent]`, this control goes green — and a green negative control is the
        defect, not the pass.
        """
        kind = "synthetic_generic_prompt"
        pattern = pp.PromptPattern(kind, re.compile("zzz-generic"))
        pp.PROMPT_PATTERNS_BY_AGENT["all"].append(pattern)
        try:
            unresolved = self._unresolved()
            for agent in rl.REVIEW_LOOP_AGENTS:
                self.assertIn(
                    (agent, kind), unresolved,
                    f"a generic '{'all'}'-group kind must be caught for {agent}")
            # ...and the documented escape really is the exemption table.
            for agent in rl.REVIEW_LOOP_AGENTS:
                rl.DELIBERATELY_UNANCHORED_KINDS[(agent, kind)] = "test"
            try:
                self.assertEqual(self._unresolved(), [])
            finally:
                for agent in rl.REVIEW_LOOP_AGENTS:
                    rl.DELIBERATELY_UNANCHORED_KINDS.pop((agent, kind), None)
        finally:
            pp.PROMPT_PATTERNS_BY_AGENT["all"].remove(pattern)
        self.assertEqual(self._unresolved(), [])  # restored


class PerAgentBlockBoundaryTests(unittest.TestCase):
    """`classify_followed_change` must use the pane's OWN block boundary.

    Measuring a Codex pane against Claude's chip returns None, which collapses
    to UNKNOWN — safe, but it silently disables selection-only classification.
    """

    def _codex_widget(self, question: str, selected: int) -> str:
        options = "\n".join(
            f"  {'›' if i == selected else ' '} {i}. option {i}"
            for i in range(1, 4))
        return ("  Question 1/1 (1 unanswered)\n"
                f"  {question}\n"
                f"{options}\n"
                "  tab to add notes | enter to submit answer | esc to interrupt")

    def test_codex_selection_only_is_classified(self):
        prev = self._codex_widget("Pick one", 1)
        curr = self._codex_widget("Pick one", 2)
        self.assertEqual(
            rl.classify_followed_change(prev, "codex_question", curr,
                                        "codex_question", True, "codex"),
            rl.SELECTION_ONLY)

    def test_codex_scrollback_growth_above_the_block_is_work(self):
        prev = self._codex_widget("Pick one", 1)
        curr = "new agent output\n" + self._codex_widget("Pick one", 1) + " "
        self.assertEqual(
            rl.classify_followed_change(prev, "codex_question", curr,
                                        "codex_question", True, "codex"),
            rl.WORK)


class NativeDialogBoundaryTests(unittest.TestCase):
    """Native (chip-less) permission dialogs, on REAL captures (t1518).

    Before t1518 `NATIVE_DIALOG_BOUNDARIES` held one row, so every content
    change under a Codex or OpenCode dialog kind fell through to UNKNOWN —
    safe, but the work latch could neither open nor reset while such a dialog
    was up. Both directions are asserted per agent per dialog: a row that only
    proves the no-fire direction proves nothing, because UNKNOWN would pass it.
    """

    CODEX_KIND = "codex_permission"
    OC_KIND = "opencode_permission"

    # --- codex: cursor is a `›` glyph, so the STRIPPED text changes ---------

    def test_codex_exec_approval_selection_is_selection_only(self):
        self.assertEqual(
            rl.classify_followed_change(
                fx.CODEX_EXEC_APPROVAL_SEL1_RAW, self.CODEX_KIND,
                fx.CODEX_EXEC_APPROVAL_SEL2_RAW, self.CODEX_KIND,
                True, "codex"),
            rl.SELECTION_ONLY)

    def test_codex_exec_approval_output_above_boundary_is_work(self):
        self.assertEqual(
            rl.classify_followed_change(
                fx.CODEX_EXEC_APPROVAL_SEL1_RAW, self.CODEX_KIND,
                fx.CODEX_EXEC_APPROVAL_LATER_RAW, self.CODEX_KIND,
                True, "codex"),
            rl.WORK)

    def test_codex_selection_pair_really_differs_when_stripped(self):
        """Premise control for the two tests above.

        If the pair were stripped-identical the SELECTION_ONLY assertion would
        pass as NO_CHANGE... except it would not, and that asymmetry is the
        point: this pins WHY codex asserts SELECTION_ONLY where opencode
        asserts NO_CHANGE, so a future fixture refresh cannot silently swap the
        mechanism under either test.
        """
        self.assertNotEqual(strip(fx.CODEX_EXEC_APPROVAL_SEL1_RAW),
                            strip(fx.CODEX_EXEC_APPROVAL_SEL2_RAW))

    def test_codex_yes_proceed_shares_the_exec_approval_boundary(self):
        """Both kinds are the same dialog anchored at two distances.

        `codex_yes_proceed` was never observed as the reported kind on 0.146.0
        (its footer always wins, first-match), so this is the only place the
        row is exercised at all — which is exactly why it is asserted rather
        than trusted.
        """
        self.assertIs(
            rl.NATIVE_DIALOG_BOUNDARIES[("codex", "codex_yes_proceed")],
            rl.NATIVE_DIALOG_BOUNDARIES[("codex", "codex_permission")])
        self.assertEqual(
            rl.classify_followed_change(
                fx.CODEX_EXEC_APPROVAL_SEL1_RAW, "codex_yes_proceed",
                fx.CODEX_EXEC_APPROVAL_SEL2_RAW, "codex_yes_proceed",
                True, "codex"),
            rl.SELECTION_ONLY)

    # --- opencode: selection is pure ANSI styling ---------------------------

    def test_opencode_permission_selection_is_no_change(self):
        """NOT SELECTION_ONLY, and the difference is measured, not incidental.

        OpenCode draws its selection purely as styling, so the ANSI strip
        erases it and `classify_followed_change` returns NO_CHANGE *before*
        reaching any boundary. Both verdicts are equally non-firing, so the
        loop is safe either way — but asserting the wrong one here would hide a
        real regression: if a future OpenCode drew a glyph cursor instead, this
        test would start failing and the boundary would need re-measuring.
        """
        self.assertEqual(
            rl.classify_followed_change(
                fx.OPENCODE_PERMISSION_SEL1_RAW, self.OC_KIND,
                fx.OPENCODE_PERMISSION_SEL2_RAW, self.OC_KIND,
                True, "opencode"),
            rl.NO_CHANGE)

    def test_opencode_selection_pair_moved_but_strips_identical(self):
        """Ground-truth control for the test above.

        The RAW frames must differ (the selection genuinely moved) while the
        stripped frames must not. Without the raw half, a fixture pair captured
        from a keypress that never registered would satisfy the NO_CHANGE
        assertion vacuously — which is precisely what happened during the
        t1518 measurement when `Tab` was sent instead of `Right`.
        """
        self.assertNotEqual(fx.OPENCODE_PERMISSION_SEL1_RAW,
                            fx.OPENCODE_PERMISSION_SEL2_RAW)
        self.assertEqual(strip(fx.OPENCODE_PERMISSION_SEL1_RAW),
                         strip(fx.OPENCODE_PERMISSION_SEL2_RAW))

    def test_opencode_permission_output_above_boundary_is_work(self):
        """The direction the boundary row actually exists for."""
        self.assertEqual(
            rl.classify_followed_change(
                fx.OPENCODE_PERMISSION_SEL1_RAW, self.OC_KIND,
                fx.OPENCODE_PERMISSION_LATER_RAW, self.OC_KIND,
                True, "opencode"),
            rl.WORK)

    # --- the phrase/structural branch, pinned to what shipped ---------------

    def test_exactly_one_mechanism_carries_opencode_permission(self):
        """Both tables are always defined; only the ENTRY is branch-dependent.

        Asserting on symbol existence would assert the wrong thing — the
        strategy table ships empty precisely so the precedence lookup in
        `classify_followed_change` is unconditional.
        """
        key = ("opencode", "opencode_permission")
        in_regex = key in rl.NATIVE_DIALOG_BOUNDARIES
        in_strategy = key in rl.NATIVE_DIALOG_STRATEGIES
        self.assertNotEqual(in_regex, in_strategy,
                            "exactly one mechanism must carry the key")
        # t1518 measured the two equivalent and selected the phrase branch.
        self.assertTrue(in_regex)
        self.assertFalse(in_strategy)

    def test_strategy_mechanism_resolves_a_block_start(self):
        """The callable arm of the precedence lookup, proven by execution.

        The shipped strategy table is empty, so nothing in production takes
        this arm today — it would be an unexercised path, and an unexercised
        lookup is how a nominal table gets shipped. Register a synthetic entry
        and drive both directions through it.
        """
        kind = "synthetic_native_kind"
        key = ("opencode", kind)
        marker = "=== SYNTHETIC BLOCK START ==="

        def start(lines):
            for idx in range(len(lines) - 1, -1, -1):
                if marker in lines[idx]:
                    return idx
            return None

        block = f"{marker}\n  option a\n  option b"
        prev = "shared scrollback\n" + block + "\n> a"
        curr = "shared scrollback\n" + block + "\n> b"
        grew = "shared scrollback\nNEW OUTPUT\n" + block + "\n> a"
        with patched_strategy(key, start):
            self.assertEqual(
                rl.classify_followed_change(prev, kind, curr, kind,
                                            True, "opencode"),
                rl.SELECTION_ONLY)
            self.assertEqual(
                rl.classify_followed_change(prev, kind, grew, kind,
                                            True, "opencode"),
                rl.WORK)
        # ...and it is really gone again, so the table stays empty as shipped.
        self.assertNotIn(key, rl.NATIVE_DIALOG_STRATEGIES)

    def test_strategy_returning_none_is_unknown_not_a_fallback(self):
        """Negative control for the test above.

        A strategy that cannot locate its block must yield UNKNOWN. If the
        regex table were consulted anyway (precedence bug), a kind with both
        entries would silently classify through the wrong mechanism.
        """
        kind = "synthetic_native_kind"
        key = ("opencode", kind)
        with patched_strategy(key, lambda lines: None):
            self.assertEqual(
                rl.classify_followed_change("a", kind, "b", kind,
                                            True, "opencode"),
                rl.UNKNOWN)

    def test_strategy_table_wins_over_the_regex_table(self):
        """Precedence, asserted directly rather than inferred from ordering.

        Register a strategy for a kind the REGEX table already anchors; the
        strategy's index must be the one used. Pinned because the two tables
        agreeing by accident would hide a reversed lookup.
        """
        key = ("codex", "codex_permission")
        self.assertIn(key, rl.NATIVE_DIALOG_BOUNDARIES)  # premise
        with patched_strategy(key, lambda lines: None):
            self.assertEqual(
                rl.classify_followed_change(
                    fx.CODEX_EXEC_APPROVAL_SEL1_RAW, "codex_permission",
                    fx.CODEX_EXEC_APPROVAL_SEL2_RAW, "codex_permission",
                    True, "codex"),
                rl.UNKNOWN,
                "the strategy table must be consulted before the regex table")


class ClaudePermissionBoundaryTests(unittest.TestCase):
    """Claude's tool-permission dialog boundary (t1540), on real captures.

    Three geometries because pane height decides which KIND is reported, and
    both kinds carry the same row. A test at 120x30 alone would leave the
    geometry the review loop actually runs in — a shadow-split pane — unproven.
    """

    # (label, sel1, sel2, later, expected kind)
    GEOMETRIES = (
        ("120x30", "CLAUDE_PERMISSION_SEL1_RAW", "CLAUDE_PERMISSION_SEL2_RAW",
         "CLAUDE_PERMISSION_LATER_RAW", "claude_help_bar"),
        ("120x14", "CLAUDE_PERMISSION_COMPACT_SEL1_RAW",
         "CLAUDE_PERMISSION_COMPACT_SEL2_RAW",
         "CLAUDE_PERMISSION_COMPACT_LATER_RAW", "claude_help_bar"),
        ("120x6", "CLAUDE_PERMISSION_SHORT_SEL1_RAW",
         "CLAUDE_PERMISSION_SHORT_SEL2_RAW",
         "CLAUDE_PERMISSION_SHORT_LATER_RAW", "claude_proceed"),
    )

    def test_every_geometry_carries_a_full_trio(self):
        """Premise control: no geometry may opt out of a direction.

        An earlier revision left 120x6 without a LATER frame, so the shipped
        `claude_proceed` row had its no-fire direction proven and its WORK
        direction not proven at all — a row could suppress cursor movement
        correctly and still fail to notice real output in the short-pane
        regime. Asserted structurally so the gap cannot reopen by someone
        setting a fixture back to None.
        """
        for label, s1, s2, later, _kind in self.GEOMETRIES:
            with self.subTest(geometry=label):
                for slot, name in (("sel1", s1), ("sel2", s2), ("later", later)):
                    self.assertIsNotNone(name, f"{label} has no {slot} fixture")
                    self.assertTrue(hasattr(fx, name), name)

    def test_selection_is_selection_only_at_every_geometry(self):
        for label, s1, s2, _later, kind in self.GEOMETRIES:
            with self.subTest(geometry=label):
                self.assertEqual(
                    rl.classify_followed_change(
                        getattr(fx, s1), kind, getattr(fx, s2), kind,
                        True, "claude"),
                    rl.SELECTION_ONLY)

    def test_output_above_the_boundary_is_work(self):
        """The direction the boundary row actually exists for."""
        for label, s1, _s2, later, kind in self.GEOMETRIES:
            with self.subTest(geometry=label):
                self.assertEqual(
                    rl.classify_followed_change(
                        getattr(fx, s1), kind, getattr(fx, later), kind,
                        True, "claude"),
                    rl.WORK)

    def test_selection_pair_really_differs_when_stripped(self):
        """Premise control: Claude draws a `❯` glyph, so the no-fire result
        must come from the boundary comparison and not from the two frames
        being stripped-identical (which would return NO_CHANGE first and make
        the assertion above vacuous)."""
        for label, s1, s2, _later, _kind in self.GEOMETRIES:
            with self.subTest(geometry=label):
                self.assertNotEqual(strip(getattr(fx, s1)),
                                    strip(getattr(fx, s2)))

    def test_both_kinds_share_one_boundary_object(self):
        """Same dialog, two kinds selected by pane height — so they must not
        drift into two literals that can be edited apart."""
        self.assertIs(rl.NATIVE_DIALOG_BOUNDARIES[("claude", "claude_help_bar")],
                      rl.NATIVE_DIALOG_BOUNDARIES[("claude", "claude_proceed")])

    def test_boundary_and_prompt_pattern_share_one_object(self):
        """Same line of the same dialog, two layers — t1557.

        The boundary locates the dialog block; the prompt pattern selects the
        reported kind. Different roles, one literal, and they must not drift:
        they already did once, when t1540 tightened the boundary to a whole-line
        anchor and left the kind selector a substring — so a user typing the
        phrase into the editable option row flipped the kind and fired the loop,
        short-circuiting ahead of this boundary entirely.
        """
        proceed = [p for p in pp.PROMPT_PATTERNS_BY_AGENT["claude"]
                   if p.name == "claude_proceed"]
        self.assertEqual(len(proceed), 1, "premise: exactly one claude_proceed")
        self.assertIs(proceed[0].regex, rl._CLAUDE_PERMISSION_RE)
        self.assertIs(proceed[0].regex,
                      rl.NATIVE_DIALOG_BOUNDARIES[("claude", "claude_proceed")])

    def test_exactly_one_mechanism_carries_each_claude_permission_kind(self):
        for kind in ("claude_help_bar", "claude_proceed"):
            key = ("claude", kind)
            with self.subTest(kind=kind):
                self.assertNotEqual(key in rl.NATIVE_DIALOG_BOUNDARIES,
                                    key in rl.NATIVE_DIALOG_STRATEGIES,
                                    "exactly one mechanism must carry the key")

    def test_reported_kind_is_geometry_dependent_as_measured(self):
        """Pins the two rendering regimes through the PRODUCTION classifier.

        This is what justifies shipping a row for `claude_proceed` at all: it
        is reachable, unlike t1518's `codex_yes_proceed`. If a future Claude
        version stops truncating the option list, this fails and the row's
        justification must be re-measured rather than quietly inherited.
        """
        for label, s1, _s2, _later, expected in self.GEOMETRIES:
            with self.subTest(geometry=label):
                res = mc.classify_content(
                    getattr(fx, s1), mc.DEFAULT_COMPARE_MODE,
                    pp.all_patterns(), mc.PaneCategory.AGENT, "claude")
                self.assertTrue(res.awaiting_input)
                self.assertEqual(res.awaiting_input_kind, expected)

    def test_option_two_frame_is_detected(self):
        """The specific defect t1540 fixed, pinned at its cause.

        On 2.1.233 the option-2 help bar drops `Tab to amend`. Before the
        pattern was widened this frame reported NO kind, `awaiting_input` went
        True->False, and `classify_followed_change` short-circuited to WORK on
        a pure cursor move — before any boundary lookup. Assert the frame is
        detected, not merely that the pair classifies SELECTION_ONLY: the pair
        would also pass if both frames were undetected.
        """
        for label, _s1, s2, _later, expected in self.GEOMETRIES:
            with self.subTest(geometry=label):
                res = mc.classify_content(
                    getattr(fx, s2), mc.DEFAULT_COMPARE_MODE,
                    pp.all_patterns(), mc.PaneCategory.AGENT, "claude")
                self.assertTrue(
                    res.awaiting_input,
                    "option-2 frame must report a kind; a cursor move that "
                    "loses detection classifies WORK and fires the loop")
                self.assertEqual(res.awaiting_input_kind, expected)


class ScopedBoundaryDoesNotOverreachTests(unittest.TestCase):
    """`claude_help_bar` is Claude's GENERIC blocked-on-input footer, but the
    boundary was measured against the tool-permission dialog only. Nothing but
    the regex enforces that scope, so a frame that is not that dialog must
    still fail to anchor — the pre-t1540 behaviour, preserved deliberately."""

    #: Every non-permission Claude surface captured in the fixture set, as
    #: REAL frames rather than one representative. A single sample could pass
    #: because that one screen happens not to contain the phrase; the point is
    #: that no live Claude surface outside the permission dialog does.
    #: fixture -> the kind production actually reports for it.
    NON_DIALOG = {
        "CLAUDE_NO_DIALOG_AT_REST_RAW": "",            # at rest, t1540 capture
        "CLAUDE_AT_REST_RAW": "",                      # at rest, t1159_2
        "CLAUDE_TYPED_RAW": "",                        # composer holds text
        "CLAUDE_STREAMING_RAW": "",                    # agent producing output
        "ASKUSER_SEL1": "claude_askuserquestion",      # numbered-selection widget
        "CLAUDE_DIALOG_RAW": "claude_askuserquestion",  # numbered-selection widget
        "PLAN_SEL1": "claude_plan_approval",           # plan-related surface
        "PLAN_REVISED": "claude_plan_approval",        # plan-related surface
    }

    def test_no_other_claude_surface_reports_the_help_bar_kind(self):
        """The widening is bounded — asserted, not assumed.

        t1540 relaxed `claude_help_bar` to accept either affordance of the
        permission dialog's footer. If that reached another surface, the
        boundary below would start anchoring a dialog nobody measured.

        The table deliberately spans BOTH protection classes, because they are
        not equally safe. Matching is first-wins and `claude_help_bar` is
        listed last, so a surface that already has its own earlier pattern
        (`claude_askuserquestion`, `claude_plan_approval`) is protected
        structurally — widening the help-bar regex cannot steal it. The frames
        that report NO kind (at rest, typed, streaming) have no such shield,
        and they are the ones an over-broad widening actually captures. A
        negative control that mutates the regex to reach a *shielded* surface
        passes and proves nothing; it has to target a pattern-less one.
        """
        for name, expected in self.NON_DIALOG.items():
            with self.subTest(fixture=name):
                res = mc.classify_content(
                    getattr(fx, name), mc.DEFAULT_COMPARE_MODE,
                    pp.all_patterns(), mc.PaneCategory.AGENT, "claude")
                self.assertEqual(res.awaiting_input_kind, expected)
                self.assertNotEqual(res.awaiting_input_kind, "claude_help_bar")

    def test_non_dialog_frames_do_not_anchor(self):
        for name in self.NON_DIALOG:
            raw = strip(getattr(fx, name))
            with self.subTest(fixture=name):
                self.assertIsNone(
                    rl._native_block_start(raw.splitlines(), "claude",
                                           "claude_help_bar"),
                    "the boundary must not locate a block on a frame that is "
                    "not the permission dialog")

    def test_non_dialog_change_under_the_kind_is_unknown(self):
        """Both halves are required. Asserting only UNKNOWN would pass
        vacuously if the two frames happened to be stripped-identical, since
        NO_CHANGE returns before any boundary lookup.

        The kind is FORCED to `claude_help_bar` here even though production
        reports something else for these frames: that is the hostile case —
        the row must stay inert on a surface it never measured even if the
        kind arrives from somewhere else.
        """
        for name in self.NON_DIALOG:
            raw = getattr(fx, name)
            with self.subTest(fixture=name):
                self.assertEqual(
                    rl.classify_followed_change(
                        raw, "claude_help_bar",
                        raw + "\nnew output line", "claude_help_bar",
                        True, "claude"),
                    rl.UNKNOWN)

    def test_typed_phrase_cannot_relocate_the_boundary_onto_an_option_row(self):
        """User-typed text must not become the boundary.

        The dialog's option rows are EDITABLE (Tab amends option 1), so typing
        the boundary phrase into one puts a second copy BELOW the real header.
        `_boundary_index` takes the LAST match, so a substring anchor would
        resolve the boundary to that option row — a line that MOVES during
        selection, which is exactly what B4 exists to forbid, and reachable
        from user input rather than from CLI churn.

        The shipped anchor requires the line to hold nothing but the question,
        so the copy (` ❯ 1. Yes, <typed text>`) is rejected and the real header
        still wins. Asserted as an index identity against the whole-line
        occurrence, not a literal, so the fixture and the assertion cannot
        drift apart.
        """
        for name in ("CLAUDE_AMEND_TYPED_PHRASE_RAW",
                     "CLAUDE_AMEND_TYPED_SEL1_RAW",
                     "CLAUDE_AMEND_TYPED_SEL2_RAW"):
            lines = strip(getattr(fx, name)).splitlines()
            hits = [i for i, line in enumerate(lines)
                    if "Do you want to proceed?" in line]
            with self.subTest(fixture=name):
                self.assertEqual(len(hits), 2,
                                 "premise: the fixture must hold the real "
                                 "question AND a typed copy")
                whole = [i for i in hits
                         if lines[i].strip() == "Do you want to proceed?"]
                self.assertEqual(len(whole), 1, "exactly one whole-line header")
                start = rl._native_block_start(lines, "claude", "claude_proceed")
                self.assertEqual(start, whole[0],
                                 "the boundary must resolve to the real header")
                self.assertLess(start, max(hits),
                                "the typed copy sits BELOW the header — if the "
                                "boundary had resolved to it, an editable, "
                                "moving line would be anchoring the block")

    def test_typed_state_selection_pair_is_still_no_fire(self):
        """The B4 assertion for the typed state, which was missing.

        Documenting the reproduction case is not enough: the state needs the
        same both-directions treatment as every other, or a cursor move made
        while the phrase is typed has no assertion at all.
        """
        self.assertEqual(
            rl.classify_followed_change(
                fx.CLAUDE_AMEND_TYPED_SEL1_RAW, "claude_proceed",
                fx.CLAUDE_AMEND_TYPED_SEL2_RAW, "claude_proceed",
                True, "claude"),
            rl.SELECTION_ONLY)


class OrderedStateNegativeHalfTests(unittest.TestCase):
    """The OTHER consumer of `PROMPT_PATTERNS_BY_AGENT` (t1557).

    `_ordered_state`'s negative half scans the WHOLE captured tail — deliberately
    wider than `classify_content`'s bottom-6-line window — and returns
    `SHADOW_DIALOG` on any pattern hit. Narrowing `claude_proceed` to a
    whole-line anchor therefore reaches this consumer too, so the reach is
    characterized here rather than assumed.

    **Not pinned through `shadow_prompt_ready` / `_claude_state`, deliberately.**
    Such a pin is vacuous: `_composer_state`'s positive half returns
    `SHADOW_DIALOG` the moment it sees an option row, before the pattern loop can
    matter, so a `_claude_state` assertion holds for any pattern whatsoever —
    including none at all. `test_claude_state_verdict_is_carried_by_structure`
    below proves that, so nobody rebuilds the vacuous pin.

    The probe forces the positive half to `SHADOW_READY` and hands it a
    never-matching `working_re`, leaving the pattern loop as the only thing that
    can answer `SHADOW_DIALOG`. `_ordered_state`'s signature is preserved verbatim
    for exactly this use (see its docstring).

    Written green against the UNMODIFIED module first: every row below held
    before the tightening, and the change moves exactly one cell
    (`test_typed_copy_alone_no_longer_claims_a_dialog`, `dialog` -> `ready`).
    """

    _NEVER = re.compile(r"(?!x)x")
    _HEADER = "Do you want to proceed?"

    #: Real captures the pattern loop must keep answering for.
    REAL = ("CLAUDE_PERMISSION_COMPACT_SEL1_RAW",
            "CLAUDE_PERMISSION_SHORT_SEL1_RAW",
            "CLAUDE_AMEND_TYPED_SEL1_RAW")

    @staticmethod
    def _ready(raw_text, plain):
        return rl.SHADOW_READY

    def _pattern_verdict(self, raw):
        return rl._ordered_state(raw, agent="claude", positive=self._ready,
                                 working_re=self._NEVER)

    def _drop(self, raw, *, header=False, help_bar=False):
        """The RAW capture with whole lines removed, selected on stripped text."""
        kept = []
        for line in raw.split("\n"):
            plain = strip(line)
            if header and plain.strip() == self._HEADER:
                continue
            if help_bar and "Esc" in plain and "cancel" in plain:
                continue
            kept.append(line)
        return "\n".join(kept)

    def _assert_only_the_typed_copy_survives(self, raw):
        lines = strip(raw).splitlines()
        self.assertTrue(any(self._HEADER in line for line in lines),
                        "premise: the user-typed copy must survive the drop")
        self.assertFalse(any(line.strip() == self._HEADER for line in lines),
                         "premise: no whole-line occurrence may survive")

    def test_probe_scaffolding_is_inert(self):
        """Premise control for the probe itself.

        If `_ready` did not force READY, or `_NEVER` matched something, every
        verdict below would come from the scaffolding instead of the patterns.
        """
        self.assertIsNone(self._NEVER.search(self._HEADER))
        self.assertEqual(self._ready("x", "x"), rl.SHADOW_READY)

    def test_real_permission_frames_still_hit_the_pattern_loop(self):
        for name in self.REAL:
            with self.subTest(fixture=name):
                self.assertEqual(self._pattern_verdict(getattr(fx, name)),
                                 rl.SHADOW_DIALOG)

    def test_help_bar_carries_the_frame_once_the_header_is_gone(self):
        """Header dropped, help bar kept: `claude_help_bar` still answers.

        The middle row of the flip table, and the reason the row below is a
        bounded change rather than a loss of coverage.
        """
        raw = self._drop(fx.CLAUDE_AMEND_TYPED_SEL1_RAW, header=True)
        self._assert_only_the_typed_copy_survives(raw)
        self.assertEqual(self._pattern_verdict(raw), rl.SHADOW_DIALOG)

    def test_typed_copy_alone_no_longer_claims_a_dialog(self):
        """The one cell the tightening moves.

        Header AND help bar dropped, so the user-typed copy in the editable
        option row is the only remaining occurrence of the phrase and the only
        thing any pattern could match. Under the substring anchor
        `claude_proceed` answered `SHADOW_DIALOG` here — user-typed prose
        claiming a dialog in a consumer that scans the whole tail. It now
        answers `SHADOW_READY`: the intended, bounded effect of t1557.
        """
        raw = self._drop(fx.CLAUDE_AMEND_TYPED_SEL1_RAW,
                         header=True, help_bar=True)
        self._assert_only_the_typed_copy_survives(raw)
        self.assertEqual(
            [p.name for p in pp.PROMPT_PATTERNS_BY_AGENT["claude"]
             if p.regex.search(strip(raw))],
            [],
            "premise: no claude pattern may match this frame any more")
        self.assertEqual(self._pattern_verdict(raw), rl.SHADOW_READY)

    def test_claude_state_verdict_is_carried_by_structure(self):
        """Production is unmoved — and the reason is structural, not the pattern.

        `_claude_state` answers `SHADOW_DIALOG` for every frame above, derived
        ones included, and keeps doing so with the claude pattern group emptied
        entirely. That second half is why the assertions above probe
        `_ordered_state` directly: a `_claude_state` pin cannot fail on a pattern
        change, so it is not a control for one.
        """
        typed = fx.CLAUDE_AMEND_TYPED_SEL1_RAW
        frames = [(n, getattr(fx, n)) for n in self.REAL] + [
            ("header dropped", self._drop(typed, header=True)),
            ("header+help bar dropped",
             self._drop(typed, header=True, help_bar=True))]
        for label, raw in frames:
            with self.subTest(frame=label):
                self.assertEqual(rl._claude_state(raw), rl.SHADOW_DIALOG)
        with patched_claude_patterns([]):
            for label, raw in frames:
                with self.subTest(frame=label, patterns="none"):
                    self.assertEqual(
                        rl._claude_state(raw), rl.SHADOW_DIALOG,
                        "a _claude_state assertion cannot fail on a pattern "
                        "change — do not build one and call it coverage")


class TypedAmendCannotFlipTheReportedKindTests(unittest.TestCase):
    """The permission dialog's option 1 is EDITABLE (`Tab` amends it) — t1557.

    With a substring `claude_proceed`, typing the boundary phrase into that row
    put a second copy of it INSIDE `_prompt_detection_text`'s bottom-6-line
    window while the real header stayed outside it. The reported kind flipped
    `claude_help_bar` -> `claude_proceed` mid-dialog, and
    `classify_followed_change` short-circuits to WORK on `prev_kind !=
    curr_kind` — so a spurious auto-recheck round fired while the user was still
    typing. t1540 closed the same hole in the BOUNDARY; this pins the KIND
    selector, which is the layer that short-circuits ahead of it.

    The typed frames are real captures. The "before typing" frame is derived from
    each by removing the amend text from its option-1 row, so everything above
    the boundary is byte-identical — the derived-frame idiom this file already
    uses in `test_non_dialog_change_under_the_kind_is_unknown`. No pair of real
    captures can serve: the shipped dialog frames were captured from different
    commands, so their text ABOVE the boundary differs and they classify WORK for
    a legitimate reason.
    """

    #: Option-1 row as captured -> the same row without the amend text. Two
    #: variants because the selected row carries `❯` and its own styling while
    #: the unselected one does not; substituted on the RAW frame so the ANSI
    #: styling survives into `_claude_state`-style consumers.
    _AMEND_ROWS = {
        "\x1b[38;5;153mYes, \x1b[39mDo you want to proceed?":
            "\x1b[38;5;153mYes\x1b[39m",
        "Yes, Do you want to proceed?": "Yes",
    }

    TYPED = ("CLAUDE_AMEND_TYPED_PHRASE_RAW",
             "CLAUDE_AMEND_TYPED_SEL1_RAW",
             "CLAUDE_AMEND_TYPED_SEL2_RAW")

    #: A real UNtyped capture of the same dialog at the same geometry (120x14).
    UNTYPED_CAPTURE = "CLAUDE_PERMISSION_COMPACT_SEL1_RAW"

    def _untyped(self, raw):
        hits = [row for row in self._AMEND_ROWS if row in raw]
        self.assertEqual(len(hits), 1,
                         "premise: the fixture must carry exactly one typed "
                         "option row")
        return raw.replace(hits[0], self._AMEND_ROWS[hits[0]])

    @staticmethod
    def _kind(raw):
        res = mc.classify_content(raw, mc.DEFAULT_COMPARE_MODE,
                                  pp.all_patterns(), mc.PaneCategory.AGENT,
                                  "claude")
        return res.awaiting_input, res.awaiting_input_kind

    def test_typed_copy_is_inside_the_window_and_the_header_is_not(self):
        """Premise control: without this geometry the defect cannot occur.

        The whole bug is that the two occurrences fall on opposite sides of
        `_prompt_detection_text`'s boundary. If a future capture moved either
        one, the tests below would keep passing while testing nothing.
        """
        for name in self.TYPED:
            window = mc._prompt_detection_text(strip(getattr(fx, name)))
            lines = window.splitlines()
            with self.subTest(fixture=name):
                self.assertTrue(
                    any("Do you want to proceed?" in line for line in lines),
                    "the typed copy must be inside the detection window")
                self.assertFalse(
                    any(line.strip() == "Do you want to proceed?"
                        for line in lines),
                    "the real header must be OUTSIDE the detection window")

    def test_untyped_and_typed_frames_really_differ_when_stripped(self):
        """Premise control, so SELECTION_ONLY cannot be a vacuous NO_CHANGE."""
        for name in self.TYPED:
            typed = getattr(fx, name)
            with self.subTest(fixture=name):
                self.assertNotEqual(strip(self._untyped(typed)), strip(typed))

    def test_typing_the_phrase_does_not_change_the_reported_kind(self):
        """Cross-surface parity, asserted surface-vs-surface.

        The typed frame must report what its own untyped derivation reports AND
        what a real untyped capture of the same dialog reports — not merely "not
        `claude_proceed`", which a broken pattern reporting nothing would also
        satisfy.
        """
        real_untyped = self._kind(getattr(fx, self.UNTYPED_CAPTURE))
        self.assertEqual(real_untyped, (True, "claude_help_bar"),
                         "premise: the untyped dialog reports the help bar")
        for name in self.TYPED:
            typed = getattr(fx, name)
            with self.subTest(fixture=name):
                self.assertEqual(self._kind(typed),
                                 self._kind(self._untyped(typed)))
                self.assertEqual(self._kind(typed), real_untyped)

    def test_dialog_to_typed_transition_is_not_work(self):
        """The defect at its cause, through the production classifier.

        Kinds are taken from `classify_content` rather than hand-supplied: a
        hand-supplied pair would pin the boundary comparison (already covered)
        and step right over the kind flip, which is what actually fired the loop.
        """
        for name in self.TYPED:
            typed = getattr(fx, name)
            untyped = self._untyped(typed)
            with self.subTest(fixture=name):
                verdict = rl.classify_followed_change(
                    untyped, self._kind(untyped)[1],
                    typed, self._kind(typed)[1],
                    True, "claude")
                self.assertNotEqual(verdict, rl.WORK,
                                    "typing into the editable option row fired "
                                    "the review loop")
                self.assertEqual(verdict, rl.SELECTION_ONLY)


class SelectionNeverClassifiesWorkTests(unittest.TestCase):
    """B4, the cross-geometry invariant (t1540).

    A pure option-cursor move must never classify WORK for ANY agent, kind or
    geometry: that is the false-positive direction, and it is the exact symptom
    of a boundary located at or below a line that moves during selection.

    Deliberately table-driven and total rather than one assertion per pair. The
    per-row tests pin each pair individually; this pins the PROPERTY, so a pair
    added later for a geometry nobody re-measured is covered on arrival.
    """

    # name -> (prev, curr, kind, agent)
    PAIRS = {
        "claude/permission 120x30": ("CLAUDE_PERMISSION_SEL1_RAW",
                                     "CLAUDE_PERMISSION_SEL2_RAW",
                                     "claude_help_bar", "claude"),
        "claude/permission 120x14": ("CLAUDE_PERMISSION_COMPACT_SEL1_RAW",
                                     "CLAUDE_PERMISSION_COMPACT_SEL2_RAW",
                                     "claude_help_bar", "claude"),
        "claude/permission 120x6": ("CLAUDE_PERMISSION_SHORT_SEL1_RAW",
                                    "CLAUDE_PERMISSION_SHORT_SEL2_RAW",
                                    "claude_proceed", "claude"),
        "claude/plan_approval": ("PLAN_SEL1", "PLAN_SEL2",
                                 "claude_plan_approval", "claude"),
        # The hostile state: the boundary phrase typed into an editable option
        # row, so a substring anchor would put the boundary on a moving line.
        "claude/permission typed-phrase": ("CLAUDE_AMEND_TYPED_SEL1_RAW",
                                           "CLAUDE_AMEND_TYPED_SEL2_RAW",
                                           "claude_proceed", "claude"),
        "codex/exec_approval": ("CODEX_EXEC_APPROVAL_SEL1_RAW",
                                "CODEX_EXEC_APPROVAL_SEL2_RAW",
                                "codex_permission", "codex"),
        "opencode/permission": ("OPENCODE_PERMISSION_SEL1_RAW",
                                "OPENCODE_PERMISSION_SEL2_RAW",
                                "opencode_permission", "opencode"),
    }

    def test_no_selection_pair_classifies_work(self):
        self.assertTrue(self.PAIRS, "premise: the table must not be empty")
        for name, (a, b, kind, agent) in self.PAIRS.items():
            with self.subTest(pair=name):
                self.assertIn(
                    rl.classify_followed_change(
                        getattr(fx, a), kind, getattr(fx, b), kind,
                        True, agent),
                    (rl.SELECTION_ONLY, rl.NO_CHANGE, rl.UNKNOWN),
                    "a pure cursor move classified WORK — the boundary sits "
                    "at or below a line that moves during selection")

    def test_table_covers_every_measured_claude_geometry(self):
        """Premise control: the invariant is only as total as its table.

        Keyed on the geometry prefix rather than on a total count, so adding a
        non-geometry entry (the typed-phrase state) does not have to be
        accounted for here — while dropping a measured geometry still fails.
        """
        geometries = {n for n in self.PAIRS
                      if n.startswith("claude/permission 120x")}
        self.assertEqual(
            geometries,
            {"claude/permission 120x30", "claude/permission 120x14",
             "claude/permission 120x6"},
            "every geometry in the t1540 measurement set must appear, or the "
            "invariant silently narrows")
        self.assertIn("claude/permission typed-phrase", self.PAIRS,
                      "the hostile typed-phrase state must stay covered")


class ConservativeDefaultSurvivesTests(unittest.TestCase):
    """The `return UNKNOWN` fallthrough is why an unmapped dialog cannot
    misfire, and t1518 widened the set of agents that reach it. Asserted
    explicitly so a later "just add a catch-all" cannot pass quietly."""

    def test_palette_is_unmapped_by_design_and_classifies_unknown(self):
        key = ("opencode", "opencode_palette")
        self.assertNotIn(key, rl.NATIVE_DIALOG_BOUNDARIES)
        self.assertNotIn(key, rl.NATIVE_DIALOG_STRATEGIES)
        self.assertIn(key, rl.DELIBERATELY_UNANCHORED_KINDS)
        self.assertEqual(
            rl.classify_followed_change("a", "opencode_palette",
                                        "b", "opencode_palette",
                                        True, "opencode"),
            rl.UNKNOWN)

    def test_claude_trust_folder_is_still_unanchored_and_unknown(self):
        """The one Claude kind t1540 did NOT anchor, and why.

        This is the surviving half of the pre-t1540 characterization. The
        other two kinds flipped (see `test_claude_permission_kinds_are_now
        _anchored`), so asserting the old three-way UNKNOWN would now be
        asserting the defect. `claude_trust_folder` stays because the kind is
        not reported at all on 2.1.233 — measured, not assumed — so no boundary
        for it could ever be consulted.
        """
        key = ("claude", "claude_trust_folder")
        self.assertNotIn(key, rl.NATIVE_DIALOG_BOUNDARIES)
        self.assertNotIn(key, rl.NATIVE_DIALOG_STRATEGIES)
        self.assertIn(key, rl.DELIBERATELY_UNANCHORED_KINDS)
        self.assertEqual(
            rl.classify_followed_change("a", "claude_trust_folder",
                                        "b", "claude_trust_folder",
                                        True, "claude"),
            rl.UNKNOWN)

    def test_claude_permission_kinds_are_now_anchored(self):
        """The flip side: both permission kinds left the exemption table.

        Pinned in BOTH directions rather than by deleting the old assertion —
        a kind must be in exactly one of the two regimes, and a future edit
        that re-exempts one while leaving its boundary row (or vice versa)
        fails here rather than silently reverting to UNKNOWN.
        """
        for kind in ("claude_help_bar", "claude_proceed"):
            key = ("claude", kind)
            self.assertIn(key, rl.NATIVE_DIALOG_BOUNDARIES, kind)
            self.assertNotIn(key, rl.DELIBERATELY_UNANCHORED_KINDS, kind)
            self.assertTrue(rl.native_dialog_anchored("claude", kind), kind)

    def test_the_exemption_reason_is_measured_not_a_placeholder(self):
        """t1518 left all three Claude kinds reading "no measured boundary
        (pre-t1518)" — a placeholder that could not be told apart from a
        forgotten row. The one remaining exemption must carry real evidence."""
        reason = rl.DELIBERATELY_UNANCHORED_KINDS[
            ("claude", "claude_trust_folder")]
        self.assertNotIn("pre-t1518", reason)
        self.assertIn("t1540", reason)

    def test_every_exemption_carries_a_reason(self):
        for key, reason in rl.DELIBERATELY_UNANCHORED_KINDS.items():
            self.assertIsInstance(reason, str, key)
            self.assertTrue(reason.strip(),
                            f"{key} is exempted with no reason")


class ComposeRecheckPromptTests(unittest.TestCase):
    def test_total_over_every_phase_and_garbage(self):
        import workflow_phase
        for phase in (*workflow_phase.PHASES, None, "", "garbage", 42):
            for rnd in (None, 1, 2, 0, -3, "x"):
                text = rl.compose_recheck_prompt(phase, rnd)
                self.assertTrue(text, (phase, rnd))
                self.assertNotIn("\n", text, (phase, rnd))
                # The t1493 routing trigger leads every variant.
                self.assertTrue(text.startswith("refetch and recheck"),
                                (phase, rnd))

    def test_round_is_named_only_when_valid(self):
        self.assertIn("round 2", rl.compose_recheck_prompt("PLAN", 2))
        self.assertNotIn("round", rl.compose_recheck_prompt("PLAN", None))
        self.assertNotIn("round 0", rl.compose_recheck_prompt("PLAN", 0))

    def test_phase_selects_wording_only(self):
        self.assertIn("plan-challenge", rl.compose_recheck_prompt("PLAN", 1))
        self.assertIn("impl-challenge",
                      rl.compose_recheck_prompt("IMPLEMENT", 1))
        self.assertIn("impl-challenge",
                      rl.compose_recheck_prompt("POSTIMPL", 1))
        generic = rl.compose_recheck_prompt("UNKNOWN", 1)
        self.assertNotIn("plan-challenge", generic)
        self.assertNotIn("impl-challenge", generic)


class AmbiguousVerdictsHoldTests(unittest.TestCase):
    """Risk-mitigation pre-phase `pin_ambiguous_verdicts_hold` (t1606).

    t1606 reroutes an AMBIGUOUS pre-Enter verdict (`SHADOW_DIALOG` /
    `SHADOW_UNKNOWN`) from auto-disarm to :meth:`abort_fire` — the loop stays
    armed and merely holds. That is only safe because of a premise which was,
    until this class, inferred rather than executable:

    ``abort_fire`` returns the controller to WAITING with the streak preserved
    and **no cooldown stamped**, so the very next tick re-permits a fire. The
    only thing preventing an immediate re-fire is that the verdict which
    caused the abort *itself* collapses to a not-``True`` readiness, so the
    trigger short-circuits into ``holding_for_shadow``.

    That holds for DIALOG/UNKNOWN/WORKING/BUSY and NOT for READY — which is
    precisely why t1606 keeps the READY/WORKING pre-Enter verdicts fatal
    instead of aborting on them. A re-fire there would re-write the prompt on
    every cycle, an unbounded key-injection spin.

    So this class pins BOTH halves. If a future detector or settle-latch
    change ever makes DIALOG read ready-``True``, the hold silently becomes
    that spin; the mapping test below fails first.
    """

    def test_verdicts_collapse_to_the_expected_readiness_tristate(self):
        """The load-bearing mapping, one case per verdict.

        ``assertIs`` rather than ``assertEqual`` on purpose: ``None`` and
        ``False`` are the pause/negative distinction the whole loop is built
        on, and ``None == False`` is False but ``assertEqual(None, False)``
        failing is not the same guarantee as pinning the identity.
        """
        self.assertIs(rl._ready_from_state(rl.SHADOW_DIALOG), False)
        self.assertIs(rl._ready_from_state(rl.SHADOW_UNKNOWN), None)
        self.assertIs(rl._ready_from_state(rl.SHADOW_WORKING), False)
        self.assertIs(rl._ready_from_state(rl.SHADOW_BUSY), False)
        self.assertIs(rl._ready_from_state(rl.SHADOW_READY), True)

    def test_a_full_streak_holds_for_every_not_true_verdict(self):
        """Every verdict t1606 may abort on must make the trigger hold."""
        for verdict in (rl.SHADOW_DIALOG, rl.SHADOW_UNKNOWN,
                        rl.SHADOW_WORKING, rl.SHADOW_BUSY):
            with self.subTest(verdict=verdict):
                ready = rl._ready_from_state(verdict)
                ctrl = rl.ReviewLoopController()
                ctrl.arm(pending_work=True)
                action = drive_to_fire(ctrl, shadow_ready=ready)
                self.assertEqual(action, rl.ACTION_NONE)
                self.assertTrue(ctrl.holding_for_shadow)
                self.assertEqual(ctrl.state, rl.WAITING)
                self.assertTrue(ctrl.armed)
                # And it keeps holding — not a one-tick pause.
                for i in range(5):
                    self.assertEqual(
                        ctrl.tick(**make_ready_kwargs(
                            now=1010 + i, shadow_ready=ready)),
                        rl.ACTION_NONE)

    def test_only_ready_authorises_the_fire(self):
        """The control: without it, a detector returning nothing but False
        would pass the test above vacuously."""
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        self.assertEqual(
            drive_to_fire(ctrl,
                          shadow_ready=rl._ready_from_state(rl.SHADOW_READY)),
            rl.ACTION_FIRE)

    def test_abort_fire_preserves_the_streak_and_stamps_no_cooldown(self):
        """The mechanism — and the reason READY must stay fatal.

        This is the half that makes the hold cheap (no re-debounce) and the
        half that makes an abort-on-READY dangerous. Pinned together because
        they are the same property seen from two sides.
        """
        ctrl = rl.ReviewLoopController()
        ctrl.arm(pending_work=True)
        self.assertEqual(drive_to_fire(ctrl), rl.ACTION_FIRE)
        token = ctrl.delivery_token
        self.assertTrue(ctrl.abort_fire(token))
        self.assertEqual(ctrl.state, rl.WAITING)
        self.assertIsNone(ctrl.fired_at, "abort must not stamp a cooldown")
        self.assertTrue(ctrl.work_seen, "abort must not close the work latch")
        # ONE tick re-permits: the streak was preserved, so a READY verdict
        # re-fires immediately rather than re-debouncing.
        self.assertEqual(ctrl.tick(**make_ready_kwargs(now=1003)),
                         rl.ACTION_FIRE)

    def test_after_an_abort_an_ambiguous_verdict_holds_instead_of_refiring(self):
        """The end-to-end statement of the t1606 abort scope's safety."""
        for verdict in (rl.SHADOW_DIALOG, rl.SHADOW_UNKNOWN):
            with self.subTest(verdict=verdict):
                ready = rl._ready_from_state(verdict)
                ctrl = rl.ReviewLoopController()
                ctrl.arm(pending_work=True)
                self.assertEqual(drive_to_fire(ctrl), rl.ACTION_FIRE)
                self.assertTrue(ctrl.abort_fire(ctrl.delivery_token))
                for i in range(5):
                    self.assertEqual(
                        ctrl.tick(**make_ready_kwargs(
                            now=1003 + i, shadow_ready=ready)),
                        rl.ACTION_NONE, verdict)
                self.assertTrue(ctrl.armed)
                self.assertTrue(ctrl.holding_for_shadow)


class ReplayDisarmUnreachabilityTests(unittest.TestCase):
    """`_service_review_loop`'s latched-False replay CANNOT auto-disarm.

    Discovered while implementing t1606, and pinned here rather than in the
    app tests because it is a property of :meth:`ReviewLoopController.tick`'s
    inputs, not of the Textual layer.

    The replay block in ``minimonitor_app._service_review_loop`` runs only
    when::

        can_consume = (agent_presence is True
                       and bool(shadow_ok and shadow_pane))

    and it then passes ``agent_present=agent_presence`` and
    ``shadow_present=(None if not shadow_ok else bool(shadow_pane))`` into
    ``tick``. The guard therefore forces BOTH to ``True``, while ``tick``'s
    only ``ACTION_AUTO_DISARM`` producer requires one of them to be ``False``.

    t1606 deleted the dead ``if replay == ACTION_AUTO_DISARM:`` block that sat
    beneath it. This test is what makes that deletion safe: if ``can_consume``
    is ever widened so the replay can observe an absence, the branch stops
    being unreachable and must be reinstated — and this test fails, saying so.
    """

    def test_no_reachable_replay_input_can_auto_disarm(self):
        reachable = []
        for agent_presence in (True, False, None):
            for shadow_ok in (True, False):
                for shadow_pane in ("%5", None, ""):
                    # Verbatim from _service_review_loop.
                    can_consume = (agent_presence is True
                                   and bool(shadow_ok and shadow_pane))
                    if not can_consume:
                        continue
                    ctrl = rl.ReviewLoopController()
                    ctrl.arm(pending_work=True)
                    replay = ctrl.tick(
                        agent_present=agent_presence,
                        shadow_present=(None if not shadow_ok
                                        else bool(shadow_pane)),
                        awaiting_input=None,
                        stale=False,
                        work_signal=rl.UNKNOWN,
                        shadow_ready=None,
                        modal_open=False,
                        now=1000.0,
                    )
                    reachable.append(
                        (agent_presence, shadow_ok, shadow_pane, replay))
                    self.assertNotEqual(
                        replay, rl.ACTION_AUTO_DISARM,
                        "the replay branch became reachable — reinstate the "
                        "disarm block deleted by t1606")
        # Not vacuous: the guard admits at least one input, so the loop above
        # actually ran. Without this an over-tight `can_consume` would make
        # the test pass by examining nothing.
        self.assertTrue(reachable, "no replay input was exercised at all")


if __name__ == "__main__":
    unittest.main(verbosity=2)
