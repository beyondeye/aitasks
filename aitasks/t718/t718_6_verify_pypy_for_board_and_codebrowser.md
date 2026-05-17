---
priority: low
effort: medium
depends: []
issue_type: performance
status: Ready
labels: [performance, tui]
created_at: 2026-05-17 10:50
updated_at: 2026-05-17 10:50
---

## Context

Follow-up to t718_5. Sibling t718_2 wired six long-running TUIs to the PyPy
fast path (`require_ait_python_fast`) on the *theoretical* grounds that
PyPy's JIT meaningfully speeds up Textual + Rich workloads. **That
assumption was never measured empirically against board or codebrowser
specifically.** Recent measurements by t718_5 against monitor/minimonitor
showed PyPy is dramatically slower than CPython on a different but also
"PyPy-friendly" workload (asyncio-heavy with low per-tick Python work),
forcing a REVERT verdict. The same skepticism should be applied to the
remaining fast-path TUIs before users on `ait setup --with-pypy` continue
to pay a startup penalty for what may not be a meaningful steady-state win.

This task verifies PyPy actually helps **`ait board`** and
**`ait codebrowser`** specifically, and reverts their fast-path wiring if
not. Settings, brainstorm_tui, stats_tui, and syncer are left out of scope
for this task (board and codebrowser are the largest Textual surfaces; if
PyPy doesn't help these, the others can be re-evaluated separately).

## Decision rule (binary, written upfront)

For each TUI independently:

- **KEEP** if PyPy yields ≥ 10% wall-clock improvement on the representative
  workload AND the cold-start regression (~150-300 ms PyPy warmup) does not
  exceed the per-launch savings over a typical session length (~30-60 s for
  board, ~2-5 min for codebrowser).
- **REVERT** otherwise — change line 12 of the launcher back to
  `require_ait_python` and document the negative result.

Tie-breaking goes to REVERT (status quo before t718_2 was CPython).

## Key Files to Modify (conditional, per TUI)

- `.aitask-scripts/aitask_board.sh` line 12 (REVERT only: `require_ait_python_fast` → `require_ait_python`)
- `.aitask-scripts/aitask_codebrowser.sh` line 12 (REVERT only)
- `aidocs/python_tui_performance.md` (always: append measurement results for both TUIs)
- `CLAUDE.md` "Project-Specific Notes" (REVERT only: extend the t718_5 entry or add a new one anchoring the negative result for board / codebrowser)

If KEEP for both: no code edits, just documentation confirming the
empirical basis.

## Reference Files for Patterns

- `aiplans/archived/p718/p718_5_*.md` (this task's sibling) — same overall
  pattern: isolated benchmark + cold-start measurement + decision rule. Note
  in particular its **methodology lesson**: when benchmarking a code path
  that has an alternate implementation behind a runtime switch (backend vs
  fallback), explicitly assert which path is exercised before believing the
  numbers. The board and codebrowser hot paths do not have such a switch,
  but the same discipline applies — verify what your benchmark is actually
  measuring.
- `aidocs/python_tui_performance.md` — perf doc. The "Compile/JIT Options"
  table claims PyPy gives "often 2-5× on Textual workloads"; this task
  empirically tests that claim against board and codebrowser specifically.
- `.aitask-scripts/board/aitask_board.py` (~5200 LOC) — the board TUI.
- `.aitask-scripts/codebrowser/` — codebrowser app + helpers (~3500 LOC).
- `.aitask-scripts/lib/python_resolve.sh` — defines `require_ait_python_fast`
  (no changes needed here).

## Implementation Plan

1. **Pre-flight verification:**
   - Confirm PyPy installed (`~/.aitask/pypy_venv/bin/python` exists).
   - Confirm both launchers currently use `require_ait_python_fast` (the
     state t718_2 wired up).
   - Capture `git diff` baseline (should be empty).

2. **Choose a measurement methodology per TUI:**

   The challenge is that board and codebrowser are *interactive* — there's
   no "tick loop" to microbenchmark cleanly. Three candidate approaches:

   a. **Textual `App.run_test()` / `Pilot` headless driver.** Spawn the
      app under Pilot, fire a scripted sequence of keypresses, measure
      total wall time. Reproducible. Best fit for both TUIs.
   b. **py-spy profile of a real session.** Launch the TUI under each
      interpreter, run a scripted tmux send-keys sequence to drive it
      through a known workload, measure with py-spy. More realistic but
      noisier; needs py-spy installed.
   c. **Cold-start + import-cost only.** Time `python -c "import
      <main_module>"` under each interpreter. Weakest signal; covers only
      one dimension. Useful as a secondary metric, not the primary one.

   Recommended: **(a) Pilot-driven** for the primary benchmark + **(c)
   cold-start** as a secondary. Skip (b) unless py-spy turns out to be
   available and the headless results are ambiguous.

3. **Define the workload per TUI:**
   - **Board:** open the board, page down 10× through all tasks, toggle
     "Show archived", filter by a label, close.
   - **Codebrowser:** open it on a large file (e.g.,
     `.aitask-scripts/monitor/monitor_app.py` at ~1800 LOC), scroll to
     bottom, scroll to top, jump to a search hit, close.

   Both workloads should run in under ~5 seconds wall time per interpreter
   so a 5-rep median is achievable in under a minute per cell.

4. **Run the benchmark under CPython baseline and PyPy** (3-5 reps per
   interpreter × per TUI). Use `AIT_USE_PYPY=0` to force CPython and
   `AIT_USE_PYPY=1` to force PyPy; both honored by `require_ait_python_fast`.

5. **Measure cold-start** (5 reps per interpreter × per TUI):
   `time python -c "import <main_module>"` against both venvs.

6. **Decide per TUI** using the decision rule. Possibilities:
   - Both KEEP → no code edits, document the win.
   - Both REVERT → both launchers revert, both lines documented.
   - Mixed → only the loser reverts; document.

7. **Apply edits (REVERT branch) or document the win (KEEP branch).**
   Edit format mirrors t718_5:
   ```diff
   -PYTHON="$(require_ait_python_fast)"
   +PYTHON="$(require_ait_python)"
   ```

8. **Documentation (always):**
   - Append a "t718_6 Empirical Verification" section to
     `aidocs/python_tui_performance.md` with workload descriptions, results
     tables (one per TUI), and per-TUI verdict.
   - If REVERT (either or both): extend the `CLAUDE.md` "Project-Specific
     Notes" entry (or add a new one) anchoring the empirical basis.

9. **Update fast-path TUI list everywhere if any REVERT:**
   - `aidocs/python_tui_performance.md` — the "Dual-venv, opt-in" row's
     TUI enumeration.
   - Possibly the `t718_3` docs (already archived, low-priority cleanup).
   - User-facing website docs that enumerate fast-path TUIs.

10. **Verification:**
    - `shellcheck` clean on any modified launchers.
    - On REVERT: `AIT_USE_PYPY=1 ./ait <tui>` falls back to CPython
      (because the launcher now uses `require_ait_python`, which ignores
      `AIT_USE_PYPY`).
    - On KEEP: `AIT_USE_PYPY=0 ./ait <tui>` still launches normally under
      CPython; `AIT_USE_PYPY=1 ./ait <tui>` launches under PyPy.

## Verification Steps

- Document baseline + PyPy timings (per-workload wall time + cold-start)
  in plan's Final Implementation Notes.
- If kept: smoke test that both TUIs still launch normally under both
  interpreters.
- If reverted: `git diff` shows expected single-line revert in the
  affected launcher(s); subsequent `./ait <tui>` launches use CPython
  regardless of `AIT_USE_PYPY`.
- `shellcheck` clean on all touched launcher scripts.

## Notes

- **Low priority + medium effort.** Like t718_5, this is exploratory
  verification work, not a feature. Effort is `medium` (rather than `low`)
  because Textual headless benchmarking via Pilot requires some setup —
  more work than the single-function microbenchmark t718_5 did.
- **Do not let this expand into a Textual upgrade or framework change.**
  Scope is strictly: measure → decide → either revert wiring or document
  the win. No source-level optimizations of board / codebrowser.
- **Sibling settings/brainstorm/stats/syncer are intentionally out of
  scope.** If this task's result shows PyPy helps board / codebrowser,
  the others can be assumed to track. If PyPy doesn't help these two,
  follow-up tasks should consider reverting the others too.
- **Depends on t718_5** archived (so the methodology pattern this task
  references is a complete artifact). No code-level dependency.
