---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: enhancement
status: Implementing
labels: [frozen, shortcuts, tui]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-18 10:34
updated_at: 2026-10-18 10:39
---

## Goal

Change the default key for **Re-pick** in the `ait frozenagent` TUI from `p` to
`P` (shift+p). Re-pick relaunches the frozen task with a fresh agent and asks
for no confirmation, so moving it off the unshifted key makes an accidental
press less likely and pairs it with `R` (Restore), which is already uppercase.

## Scope

**In scope — `ait frozenagent` only:**

- `.aitask-scripts/frozenagent/frozenagent_app.py:242` —
  `Binding("p", "repick", "Re-pick")` → `Binding("P", "repick", "Re-pick")`.
  `P` is currently unbound in `FrozenAgentApp` (its other uppercase keys are
  `G` and `R`; mixins add only `j` and `?`). Keep the action id `repick`:
  user key overrides are keyed by `(scope="frozenagent", action)`, so an
  existing override still applies after the default moves.
- Website docs that name `p` for the frozenagent re-pick:
  - `website/content/docs/tuis/frozenagent/_index.md` (~line 121, "**p — re-pick.**")
  - `website/content/docs/tuis/frozenagent/reference.md` (~line 27 key table row,
    ~line 38 "that record's `R`, `p` and `k` are …")
  - `website/content/docs/tuis/frozenagent/how-to.md` (~line 50, "**p — re-pick**")
  - Grep `website/content/docs/workflows/freeze-and-restore-agents.md` and
    `website/content/docs/commands/_index.md` for any frozenagent `p` mention.
  - Run `python3 check_links.py --build` (in `website/`) after editing.
- Tests: `tests/test_frozenagent_app.py` presses `"p"` (e.g.
  `test_repick_is_refused_without_a_task_id`, ~line 1436; also check
  `test_restore_repick_and_drop_argv`, ~line 1384) → press `"P"`. Add a check
  that a plain `p` no longer triggers re-pick (no coordinator call), so the old
  key is proven unbound, not just the new one proven bound.

**Out of scope — keep `p` unchanged:**

- `ait monitor` (`monitor_app.py:558`, `Binding("p", "repick_frozen", …)`) and
  `ait minimonitor` (`p` = pick-by-number, overloaded to re-pick on a frozen
  followed agent, `minimonitor_app.py:~3366`). In both TUIs `P` is already the
  **Parked/frozen visibility filter** (`toggle_parked_visibility`), so re-pick
  cannot move to `P` there without displacing that filter.
- Consequently the monitor-side toast in `monitor_shared.py:1145`
  ("Frozen — press R to restore, p to re-pick") and the monitor/minimonitor
  docs stay as they are. Note that the frozenagent TUI and the monitors will
  then use different keys for the same operation — mention this in the
  frozenagent docs only if it reads naturally (e.g. a short note in the key
  table), not as a version-history remark.

## Verification

- `python3 -m pytest tests/test_frozenagent_app.py` (or
  `bash tests/run_all_python_tests.sh --test-dir …`) passes.
- `bash tests/test_shortcuts_registry_coverage.sh` passes.
- In a live `ait frozenagent`, the footer shows `P Re-pick`; `P` re-picks, `p`
  does nothing; the `?` shortcut editor lists Re-pick under `P`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-18T07:39:03Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-18T07:46:42Z status=pass attempt=1 type=human
