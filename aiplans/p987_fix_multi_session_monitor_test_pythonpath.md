---
Task: t987_fix_multi_session_monitor_test_pythonpath.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
---

# Plan: Fix multi-session monitor test environment leak (t987)

## Context

`tests/test_multi_session_monitor.sh` was reported (t987, spawned from t986_1)
to fail on a clean tree with `ModuleNotFoundError: No module named 'monitor'`
because its embedded `python` invocations did not put `.aitask-scripts` on
`PYTHONPATH` after the t822_6 `monitor_core` extraction.

**That root cause is already fixed.** Commit `63089dd00` (t999, "Align
multi-session monitor test with monitor_core package…") rewrote the test to set
`PYPATH="$LIB_DIR:$MONITOR_DIR:$BOARD_DIR:$PROJECT_DIR/.aitask-scripts"` and
migrated imports to `monitor.monitor_core`. The `ModuleNotFoundError` no longer
occurs.

A **different, still-open defect** now blocks the same multi-session discovery
path the task asked to confirm end-to-end. Running the test from inside a live
tmux session, 2 of 43 assertions fail (Tier 1b "discover_panes aggregates both
sessions": `COUNT:1`, expected `COUNT:2`).

**Root cause:** `TmuxMonitor.__init__` auto-detects the pane to exclude from
discovery via `self.exclude_pane = exclude_pane or os.environ.get("TMUX_PANE")`
(`.aitask-scripts/monitor/monitor_core.py:809`). The mock-based Tier-1 tests
fabricate synthetic pane ids (`%1`, `%2`, …) and construct `TmuxMonitor`
without an explicit `exclude_pane`. When the test runs inside a real tmux
session whose current pane id (`$TMUX_PANE`) collides with a synthetic id
(commonly `%2`), that synthetic pane is silently excluded → the second session's
pane disappears → `COUNT:1`.

The production behavior is correct (a live monitor *should* exclude its own
pane). The defect is purely that the **test inherits the outer session's
`$TMUX_PANE`**. `tests/lib/tmux_isolation.sh::require_isolated_tmux` already
neutralizes the other inherited tmux context (`unset TMUX`, private
`TMUX_TMPDIR`, pinned `AITASKS_TMUX_SOCKET`), and its header explicitly names
"pane-id collisions" as a leak class it exists to prevent — but it does not
unset `TMUX_PANE`.

## Approach

Add `unset TMUX_PANE` to `require_isolated_tmux` in
`tests/lib/tmux_isolation.sh`, alongside the existing `unset TMUX` (step 1).
This is the central, hermetic fix: every tmux test sourcing the helper becomes
independent of the surrounding session's pane id, matching the helper's stated
purpose.

### File to modify

`tests/lib/tmux_isolation.sh` — in `require_isolated_tmux()`, step 1 (the
`unset TMUX` block ~line 36), also `unset TMUX_PANE` and extend the comment to
note that synthetic pane ids in mock-based tests must not collide with the
outer session's pane.

### Why central (helper) over local (test file)

- The helper's documented mandate (lines 5–8) already covers "pane-id
  collisions"; `TMUX_PANE` is part of the inherited tmux context that step 1
  is meant to detach from — `unset TMUX_PANE` is the natural sibling of the
  existing `unset TMUX`.
- It fixes the whole class for all 11 tmux tests sourcing the helper, not just
  the one symptom observed today.
- **Blast-radius check:** the only other `TMUX_PANE` references in `tests/` are
  two *comment* lines in `test_monitor_rename_window_target.sh` (no code use,
  and it does not source the isolation helper). No isolation-using test reads
  the inherited `$TMUX_PANE`; they all spawn their own isolated fixtures. So
  unsetting it cannot regress any current test.

## Scope deviation (explicit)

The task's "Suggested fix" (set PYTHONPATH) is already satisfied by t999. Per
the no-silent-AC-deviation rule, the task description will be updated to record
that PYTHONPATH is resolved and the remaining defect is the `TMUX_PANE` leak,
with the fix being `unset TMUX_PANE` in the isolation helper. (Task-file edit,
committed via `./ait git`.)

## Verification

1. From inside a live tmux session (the failing condition):
   ```bash
   bash tests/test_multi_session_monitor.sh
   ```
   Expect `Results: 43/43 passed, 0 failed`, exit 0. (Pre-fix: 41/43, exit 1.)
2. Sanity-check a sibling isolation-using tmux test is unaffected:
   ```bash
   bash tests/test_kill_agent_pane_smart.sh
   bash tests/test_multi_session_primitives.sh
   ```
3. Lint:
   ```bash
   shellcheck tests/lib/tmux_isolation.sh
   ```

## Risk

Two dimensions assessed separately (see Risk Evaluation Procedure).

- **Code-health risk: low.** One-line addition to a test-only isolation helper,
  symmetric with an existing line. No production code changes. Blast radius
  verified (no test reads inherited `$TMUX_PANE`).
- **Goal-achievement risk: low.** Fix is empirically verified (43/43 with
  `TMUX_PANE` unset). Root cause is mechanically confirmed, not hypothesized.

No mitigations planned (before/after) — risk is low on both axes.

## Step 9 reference

Post-implementation: profile 'fast' works on the current branch (no
worktree/merge). Step 8 review + Step 9 archival apply; no branch merge step.
