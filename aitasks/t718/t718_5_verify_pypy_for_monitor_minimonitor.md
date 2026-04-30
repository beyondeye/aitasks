---
priority: low
effort: low
depends: [t718_4]
issue_type: performance
status: Ready
labels: [performance, tui]
created_at: 2026-04-30 14:31
updated_at: 2026-04-30 14:31
---

## Context

Sibling of t718_2. Parent t718 deliberately excluded `aitask_monitor.sh` and `aitask_minimonitor.sh` from the PyPy fast path under the assumption that their dominant cost is `fork+exec(tmux)` (which PyPy cannot accelerate). t719 is the planned tmux control-mode refactor for the fork/exec cost.

This task empirically tests that assumption: temporarily wire monitor and minimonitor to `require_ait_python_fast` and measure whether PyPy yields any meaningful improvement under CPython baseline vs PyPy. If yes (>10-15% on a representative workload), keep the fast-path migration. If no, revert the change and document the negative result so the assumption is empirically anchored.

This is exploratory/verification work, not a feature. The deliverable is either:
(a) the 2-line edit landing in main with measurement evidence, or
(b) the negative-result note in the parent's plan plus a CLAUDE.md Project-Specific note that PyPy is *not* worth wiring for these two TUIs.

## Key Files to Modify (transient)

- `.aitask-scripts/aitask_monitor.sh` — line 12
- `.aitask-scripts/aitask_minimonitor.sh` — line 12

Both currently have `PYTHON="$(require_ait_python)"`. Swap to `require_ait_python_fast`. Whether this edit becomes permanent depends on the measurement.

## Reference Files for Patterns

- Sibling t718_2's plan (`aiplans/archived/p718/p718_2_*.md` after archival) — same edit pattern.
- `aidocs/python_tui_performance.md` — PyPy speedup analysis. Update with measurement results from this task.

## Implementation Plan

1. **Baseline measurement (CPython):** Time a representative monitor/minimonitor workload under CPython. Suggested: launch monitor, page through 50 sessions, measure total elapsed time and tmux IPC count (use `strace -c -e fork,execve` or similar to confirm fork+exec dominates).
2. **Apply the edit:** Swap to `require_ait_python_fast` in both launchers.
3. **PyPy measurement:** Same workload, with `AIT_USE_PYPY=1` (PyPy installed via `./ait setup --with-pypy`).
4. **Decision:**
   - If PyPy improves wall-clock by >10-15% on representative workload: keep the edit, file under "performance feature" — task lands as implemented.
   - Otherwise: revert the edit, write a "Negative result" note in the parent t718 plan and `aidocs/python_tui_performance.md` confirming fork/exec dominance, leave a CLAUDE.md Project-Specific note that monitor/minimonitor stay on CPython for the foreseeable future (until t719's tmux control-mode refactor lands and the picture changes).

## Verification Steps

- Document baseline + PyPy timings in plan's Final Implementation Notes.
- If kept: `shellcheck` clean on both modified files; smoke test that `./ait monitor` still launches and renders normally with and without PyPy installed.
- If reverted: `git diff` against base shows no change to the 2 files after revert; the negative-result note is added to the parent plan and to `aidocs/python_tui_performance.md`.

## Notes

- This task is intentionally low priority — it is exploratory. It can be picked anytime after t718_2 archives. It does not block t718_3 (docs) or t718_4 (manual verification) of the originally-planned fast-path TUIs.
- Do not let this task expand into the t719 tmux control-mode refactor — that is a separate, much larger piece of work. This task is purely the 2-line swap + measurement.
