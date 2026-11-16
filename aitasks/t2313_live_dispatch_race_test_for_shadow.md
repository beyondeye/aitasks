---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [sitrep, tui, tmux]
gates: [risk_evaluated]
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-16 09:39
updated_at: 2026-11-16 09:39
---

## Origin

Risk-mitigation ("after") follow-up for t2309, created at Step 8d after implementation landed.

## Risk addressed

code-health — fake-only proof of the dispatch-time mode conjunct (no live run opens the post-read gap)

- The Enter transport of a load-bearing loop changes, and every test of it runs over hand-written fakes. A fake that mis-models the guarded `if-shell` could pass the new tests while production differs. No live run reproduces the post-read gap: the minimonitor smoke is caught by the pre-write read, and the sitrep live suite's conjunct-only mutant is declared green on (h). Step 9's baseline red proof covers the fake only. · severity: medium · → mitigation: live_dispatch_race_test_for_shadow

## Goal

t2309 closed the t2001 residual for the minimonitor shadow recheck's Enter. The Enter
is now `monitor_core.guarded_send_key`, whose `if-shell -F` condition includes
`PANE_NOT_IN_MODE`, so tmux re-checks the mode atomically with the keystroke. Two
facts mean no live test proves that conjunct for the gap it closes:

- `tests/test_minimonitor_concern_smoke.py::test_a_pane_in_copy_mode_receives_nothing_and_stays_in_mode`
  enters copy-mode **before** delivery, so the Python pre-write read catches it
  (`HOLD_SHADOW_IN_MODE`).
- `tests/test_sitrep_request_delivery_live.sh` declares its mutant
  `("only the conjunct removed", …, ["h"], False)` green, because the pre-Enter Python
  read catches case (h) first.

The proof today is the fake-backed
`ShadowPaneModeGuardTests.test_a_mode_entered_between_the_read_and_the_enter_withholds_it`
plus its HEAD red run (archived plan p2309).

Add a private-server live test in the `test_minimonitor_concern_smoke.py` harness:

1. Drive the real `_fire_shadow_recheck` / `_submit_shadow_prompt` against a real shadow
   pane.
2. Wrap `monitor_core.query_pane_mode` (and the module-level name minimonitor uses) so
   that right after the **final pre-Enter** read returns `not in a mode`, it runs
   `copy-mode -t <pane>` on the private server.
3. Assert:
   - the outcome is `("not_ready", HOLD_PRE_ENTER_IN_MODE)`, with
     `_loop_delivery_detail["enter_dispatch"] == "skipped:in_mode"`;
   - no Enter reached the mode: the pane is still in copy-mode, with no
     copy-pipe-and-cancel;
   - the composer still holds the prompt.
4. Add a mutant control that patches `monitor_core.dispatch_condition` to the identity
   term only (`run_identity_condition(...)`, as the sitrep live suite's `identity_only`
   does). The case must turn red: the Enter reaches copy-mode and the pane leaves the
   mode.

Run it under the private socket / scratch HOME rules of the existing smoke classes.
