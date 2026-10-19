---
Task: t2054_monitor_frozen_keys_only_in_frozenagent.md
Base branch: main
Output branch: main
---

# t2054 — Frozen restore/re-pick keys live only in `ait frozenagent`

## Context

In a frozen agent's window, pressing `p` in the minimonitor (to pick a follow-up
task by number) silently **re-picks the frozen task** and tears down the stand-in:
`action_pick_task_by_number` branches on the frozen state into
`action_repick_frozen` (t1705_7). User decision: frozen-specific restore/re-pick
belong to the frozen-agent viewer only (`R` restore, `P` re-pick — t2049); the
monitors keep their regular-agent key meanings.

Extra decision (user-confirmed during planning): once `p` always picks by number,
its confirm dialog's **"kill followed agent" checkbox is hidden when the followed
agent is frozen** — otherwise it would route the stand-in through
`kill_agent_pane_smart` (unleased, kill-then-drop, silently deletes the capture).
Retiring a frozen agent stays on `k` (leased `aitask_frozen.sh drop` + warning).

Working on the current branch (profile `fast`).

## Implementation steps

### 1. `.aitask-scripts/monitor/minimonitor_app.py`
1. `BINDINGS` (~:1244): delete `Binding("R", "restore_frozen", …)` and its
   comment; reword the comment to: `k` keeps its live meaning and branches on the
   frozen state inside the action; restore / re-pick are the frozen-agent viewer's
   own `R` / `P` (t2054), reached with Tab into the stand-in pane.
2. `KEY_HINTS_TEXT` (~:908): `"f:freeze  Z:all  R:restore\n"` → `"f:freeze  Z:all\n"`;
   update the budget comment above it (it says t1705_7 added `f`, `Z`, `R`) to
   record that t2054 removed `R` again. Removing text only shrinks the band.
3. `action_pick_task_by_number` (~:3373): delete the frozen branch (the
   `if snap is not None and self._is_frozen(snap): … action_repick_frozen()` block
   and its t1705_7 comment). `p` always opens `TaskNumberInputModal`.
4. `_on_pick_number_entered` (~:3410): compute `kill_label` only when
   `snap is not None and not self._is_frozen(snap)`, and set `pane_id` from the
   same condition (fail closed: no kill target ⇒ nothing to kill even if a
   payload says `True`). Comment: a frozen pane holds the stand-in viewer;
   `kill_agent_pane_smart`'s frozen path is unleased and deletes the capture
   without warning — retire it with `k`.

### 2. `.aitask-scripts/monitor/monitor_app.py`
1. `BINDINGS` (~:556): delete `Binding("p", "repick_frozen", …)` and its comment.
   The monitor then has no `p` binding.
2. `action_restart_task` (~:3811): the frozen branch no longer calls
   `action_restore_frozen()`. It notifies (warning) and returns, still **before**
   the idle check:
   `"That agent is frozen — press s to switch to its viewer, then R to restore or P to re-pick"`.
   Update the comment.
3. Frozen preview text (~:2055): `"This agent is frozen — press s to switch to its viewer, then R to restore or P to re-pick."`

### 3. `.aitask-scripts/monitor/monitor_shared.py`
1. Delete `_frozen_target`, `_start_frozen_restore`, `action_restore_frozen`,
   `action_repick_frozen` (no callers remain — verified by grep across
   `.aitask-scripts/`, `tests/`, applink).
2. `_poll_frozen_outcome`: narrow to drop-only (its only remaining caller is
   `_drop_frozen`). Signature `_poll_frozen_outcome(self, record_id)`; drop the
   `kind` / `prev_attempts` params, the `restore_settle_timeout` call and the
   `restore_verdict` branch. Remove the now-unused `_FROZEN_DISPATCH_GRACE`
   constant and the `agent_frozen_ops` import (only used there). Update the
   section note (~:990–1006) and the constants comment: these apps dispatch only
   `freeze` (subprocess) and `drop` (`run-shell -b`); restore / re-pick are the
   viewer's.
3. Freeze success toast (~:1145): `"Frozen — restore (R) or re-pick (P) from its frozen-agent viewer"`.

### 4. Keybinding registry / persisted overrides
No code change. `keybinding_registry.register_app_bindings` only consults
overrides for bindings that are registered, and the shortcut editor lists
`_DEFAULTS`, so a stale `shortcuts: {monitor: {repick_frozen: …}}` /
`{minimonitor: {restore_frozen: …}}` row becomes inert (ignored, not shown, no
error). `tests/test_shortcuts_registry_coverage.sh` is generic (no static list of
these ids) — just re-run it.

### 5. Tests
**`tests/test_monitor_frozen_filter.py`**
- Update the module docstring's `FrozenActionTests` paragraph (only `k` branches
  on frozen; restore/re-pick are the viewer's).
- Remove `test_restore_produces_the_exact_detached_argv`,
  `test_restore_warns_at_dispatch_when_the_model_is_unknown` (the coordinator's
  own model note, `agent_restore.py:906`, still covers the warning),
  `test_repick_adds_the_repick_flag`, `test_restore_and_repick_are_refused_on_a_live_agent`.
- Remove `RestorePollDeadlineTests` (~:1374–:1460). Its `_timeouts` helper calls
  `_poll_frozen_outcome(RECORD, "restore", 0)` (~:1412), so after the narrowing it
  would raise `TypeError`. The restore-deadline behaviour now exists only in the
  viewer, and `tests/test_frozenagent_app.py`'s `RestorePollDeadlineTests`
  (~:1662) already covers it: configured grace, default grace, the record's root
  rather than the cwd, the `settle_timeout=None` fallback, and in-grace-is-not-a-stall.
  Also remove the `_FakeRecord` / `_FakeTimer` helpers if nothing else uses them.
- Add `FrozenKeysBelongToTheViewerTests` (t2054):
  - no binding in either app's **MRO** `BINDINGS` (mixins included) has action
    `restore_frozen` / `repick_frozen`; `MonitorApp` binds no `p`;
    `MiniMonitorApp` binds no `R`; neither class has `action_restore_frozen` /
    `action_repick_frozen`; `KEY_HINTS_TEXT` has no `R:`.
  - monitor `R` (`action_restart_task`) on a frozen card: no `tmux_calls`, no
    `push_screen`, one warning naming the viewer and `R`/`P`. Control: a live,
    non-idle card still gets the "only available when idle" refusal (proves the
    hint comes from the frozen branch).
  - minimonitor `p` on a frozen followed agent: pushes exactly one
    `TaskNumberInputModal`, no `tmux_calls` (no `run-shell … restore`).

**`tests/test_minimonitor_pick_by_number.py`**
- `_snap(..., frozen=False)` kwarg (sets `frozen` / `frozen_record_id`); give
  `_FakeMonitor` a recording `tmux_run`.
- New tests: frozen followed agent → `p` → number modal → confirm dialog with
  `_kill_target_label is None`; `callback(("pick", True))` launches with
  `kill=None`; no `tmux_run` calls. Control: the existing live-agent kill-label
  tests stay green.

**`tests/test_monitor_markup_literal_sinks.py`**
- `_verdict_toast` becomes drop-only (call `_poll_frozen_outcome("rec-1")`, no
  `restore_settle_timeout` patch); remove the `"both: restore failed (survivor)"`
  row and `test_a_restore_failure_quotes_the_survivor_window_verbatim` (that
  toast no longer exists in the monitors; the viewer owns it). Drop the
  `agent_frozen_ops` import if unused afterwards.

**Negative control:** in an isolated scratchpad copy of `.aitask-scripts/` +
the three test files, restore the old branches (minimonitor `p` → repick,
monitor `R` → restore, the two bindings) and confirm the new tests fail; then
discard the copy.

### 6. Docs (current-state only)
- `website/content/docs/tuis/minimonitor/how-to.md` (~:351–:358): only **k**
  acts on a frozen followed agent here; to restore / re-pick, **Tab** into the
  stand-in pane and use the viewer's **R** / **P**. Key table `p` row: drop the
  frozen re-pick clause; say the dialog offers no kill checkbox when the followed
  agent is frozen (drop it with `k`).
- `website/content/docs/tuis/monitor/reference.md`: `R` row (~:33) — on a frozen
  agent it only points to the viewer (`s`, then `R`/`P`); delete the `p` row
  (~:42); preview text (~:169).
- `website/content/docs/tuis/monitor/how-to.md` (~:283–:292): only **k** acts on
  a frozen card; **R** shows a hint; restore/re-pick via `s` → viewer `R`/`P`.
- `website/content/docs/workflows/freeze-and-restore-agents.md` (~:67): replace
  the "monitors use **p**" sentence with: both keys belong to the viewer — from a
  monitor, switch into the frozen pane (`s` in `ait monitor`, `Tab` in
  `ait minimonitor`) and press them there.
- `website/content/docs/tuis/frozenagent/reference.md`: `P` row (~:27) — drop the
  "monitors use `p`" note; grace paragraph (~:105–:110) — only the viewer
  watches a restore now; See-also (~:124) "listed, filtered and revived" →
  "listed, filtered and dropped".
- Run `cd website && python3 check_links.py --build`.

## Verification
- `python3 tests/test_monitor_frozen_filter.py`
- `python3 tests/test_minimonitor_pick_by_number.py`
- `python3 tests/test_monitor_markup_literal_sinks.py`
- `python3 tests/test_minimonitor_concern_action.py` (hints ⊇ bindings parity)
- `python3 tests/test_monitor_parked_filter.py`, `tests/test_shortcut_overrides_survive.py`,
  the minimonitor top-chrome/width render tests that measure `#mini-key-hints`
- `bash tests/test_shortcuts_registry_coverage.sh`
- `grep -rn "restore_frozen\|repick_frozen\|_start_frozen_restore\|_frozen_target" .aitask-scripts` → empty
  (production code only: the new negative tests name these ids on purpose; any
  remaining test hits must be those negative assertions, nothing else)
- `bash tests/run_all_python_tests.sh --test-dir tests` (read the last line)
- `cd website && python3 check_links.py --build`

## Step 9 (Post-Implementation)
Commit code + docs (`bug: … (t2054)`), plan via `aitask_task_commit.sh`, then
archive per the workflow. Final Implementation Notes: confirm and record the
`n` path (`_launch_pick_for_own` → `kill_agent_pane_smart` on a Done frozen
stand-in, the unleased frozen path) as an upstream-defect candidate.

## Risk

### Code-health risk: medium
- Removed shared methods (`action_restore_frozen` etc.) could still have a caller somewhere (another TUI, applink, a test double), which would raise `AttributeError` on a keypress · severity: low · → mitigation: none (the plan's grep verification plus full-suite run)
- Narrowing `_poll_frozen_outcome` to drop-only removes the monitors' restore-verdict markup-sink coverage. The toast it covered is deleted with it, and the viewer keeps its own · severity: low · → mitigation: none

- Existing race, kept by this plan: the frozen guard in `_on_pick_number_entered` reads the snapshot taken when the prompt opened. `_on_pick_confirmed` checks only that the pane still exists, and `_launch_pick` kills only after another dialog. If another monitor freezes a live followed agent while these dialogs are open, a ticked kill still reaches `kill_agent_pane_smart`'s unleased frozen path and deletes the capture · severity: medium · → mitigation: recheck_frozen_before_pick_kill

### Goal-achievement risk: low
- Stand-ins started before t2049 still bind `p` = re-pick inside the viewer, so Tab-ing into one and pressing `p` still re-picks. This is out of scope per the task and goes away once the stand-ins are restarted · severity: low · → mitigation: none
- The hint and preview texts name default keys (`s`, `R`, `P`) literally and go stale if a user rebinds them. Existing texts already work this way · severity: low · → mitigation: none

### Planned mitigations
- timing: after | name: recheck_frozen_before_pick_kill | type: bug | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health race (agent frozen while the pick dialogs are open) | desc: In the minimonitor pick flow (`_on_pick_confirmed` / `_launch_pick`), re-read the kill target's current frozen state right before killing; if it is frozen now, launch without killing and say so; add a live-to-frozen transition regression test

## Final Implementation Notes
- **Actual work done:** Implemented as planned. The minimonitor `p` always opens
  the number prompt. The minimonitor `R` binding and its `R:restore` hint are
  removed. On a frozen followed agent the pick confirmation offers no kill
  checkbox, and `pane_id` is tied to that offer, so a payload that claims a kill
  reaches no target. The monitor's `p` binding is removed. The monitor's `R` on a
  frozen card shows a hint (`s` → viewer → `R`/`P`) and dispatches nothing. The
  preview text and the freeze toast point at the viewer.
  `_frozen_target` / `_start_frozen_restore` / `action_restore_frozen` /
  `action_repick_frozen` are deleted. `_poll_frozen_outcome(record_id)` handles
  drop only, and the unused `agent_frozen_ops` import and `_FROZEN_DISPATCH_GRACE`
  constant are removed. Persisted key overrides for the removed action ids are now
  inert (`register_app_bindings` only consults registered bindings): no migration
  needed.
- **Deviations from plan:** (1) Plan review: `RestorePollDeadlineTests` in
  `tests/test_monitor_frozen_filter.py` was also removed, together with its
  `_FakeRecord` / `_FakeTimer` helpers. It drove the deleted restore branch of the
  poll. `tests/test_frozenagent_app.py`'s `RestorePollDeadlineTests` covers the
  viewer's deadline. (2) Removed one more stale doc row: the minimonitor how-to
  key table had an `R` row ("Restore the followed agent when it is frozen") that
  the task did not list. (3) Also dropped the now-unused `agent_sessions` import
  from `tests/test_monitor_markup_literal_sinks.py`.
- **Issues encountered:** None. Negative control in an isolated scratchpad copy:
  every new test fails against the pre-change monitor modules. Separate
  single-guard mutants (kill guard without the frozen check, monitor `R` frozen
  branch disabled) each fail exactly their own test.
- **Key decisions:** User-confirmed during planning: hide the pick dialog's kill
  checkbox on a frozen followed agent rather than routing it to the leased drop.
  Retiring a frozen agent stays on `k`. Hint texts name the default keys
  literally, the same as the existing texts.
- **Upstream defects identified:**
  - `.aitask-scripts/monitor/minimonitor_app.py:3211-3301` — `n` (`action_pick_next_for_own` → `_launch_pick_for_own` → `_launch_pick`) has no frozen guard; when the followed task is a parent / archived / Done it kills the frozen stand-in via `kill_agent_pane_smart`, whose frozen path is an unleased kill-then-drop that deletes the capture without warning (the hazard `_drop_frozen`'s docstring describes).
- **Follow-ups created:** t2057 (review finding:
  `_find_running_agent_line` counts frozen snapshots as running, so the pick
  dialog warns "already running" for a frozen stand-in). The planned "after" risk
  mitigation `recheck_frozen_before_pick_kill` is created at Step 8d.
