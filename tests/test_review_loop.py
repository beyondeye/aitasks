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
import re
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
        # Retargeted in t1509: `codex` HAS a detector now, so it is no longer
        # an example of an unsupported agent. `opencode` is the agent that
        # still reaches the arm-time refusal, and a nonsense key covers the
        # genuinely-unknown case, so "unknown agent => indeterminate" stays
        # pinned rather than quietly losing its subject.
        self.assertIsNone(rl.shadow_prompt_ready(None, "claude", True))
        self.assertIsNone(
            rl.shadow_prompt_ready(fx.CLAUDE_AT_REST_RAW, "opencode", True))
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

    def test_the_two_dispatch_tables_cannot_drift(self):
        self.assertEqual(sorted(rl.SHADOW_READY_DETECTORS),
                         sorted(rl.SHADOW_STATE_DETECTORS))


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
    predicates, so it is asserted directly: t1467 wired Codex/OpenCode prompt
    markers, which makes the advisory phase available for them — but this loop
    INJECTS keys into the shadow pane, so it must stay Claude-only until each
    agent's boundary strategy has its own live evidence.
    """

    def test_claude_is_supported(self):
        self.assertTrue(rl.review_loop_agent_supported("claude"))

    def test_wired_agents_are_still_not_loop_supported(self):
        import workflow_phase as wp
        for agent in ("codex", "opencode"):
            self.assertTrue(
                wp.live_tiers_available(agent),
                f"{agent} should have live tiers since t1467")
            self.assertFalse(
                rl.review_loop_agent_supported(agent),
                f"{agent} must NOT be armable — the loop injects, so widening "
                f"it is its own task")

    def test_unknown_and_empty_are_not_supported(self):
        for agent in ("", "node", "python", "some_future_agent"):
            self.assertFalse(rl.review_loop_agent_supported(agent))

    def test_predicate_matches_its_constant(self):
        """Guards against the predicate and the constant drifting apart."""
        for agent in rl.REVIEW_LOOP_AGENTS:
            self.assertTrue(rl.review_loop_agent_supported(agent))


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
