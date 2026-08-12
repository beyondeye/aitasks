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

import os
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
sys.path.insert(0, str(SCRIPTS_DIR / "monitor"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_loop as rl  # noqa: E402
import review_loop_fixtures as fx  # noqa: E402


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
        self.assertIsNone(rl.shadow_prompt_ready(None, "claude", True))
        self.assertIsNone(
            rl.shadow_prompt_ready(fx.CLAUDE_AT_REST_RAW, "codex", True))
        self.assertIsNone(
            rl.shadow_prompt_ready(fx.CLAUDE_AT_REST_RAW, "", True))
        self.assertIsNone(rl.shadow_prompt_ready("", "claude", True))


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
