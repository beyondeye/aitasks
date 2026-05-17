---
Task: t718_5_verify_pypy_for_monitor_minimonitor.md
Parent Task: aitasks/t718_pypy_optional_runtime_for_tui_perf.md
Sibling Tasks: aitasks/t718/t718_4_manual_verification_pypy_optional_runtime_for_tui_perf.md
Archived Sibling Plans: aiplans/archived/p718/p718_1_pypy_infrastructure_setup_resolver.md, aiplans/archived/p718/p718_2_wire_long_running_tuis_to_fast_path.md, aiplans/archived/p718/p718_3_documentation_pypy_runtime.md
Base branch: main
plan_verified: []
---

# Plan: t718_5 — Verify PyPy for monitor / minimonitor

## Context

Child of parent t718 (PyPy optional runtime). Sibling t718_2 wired 6 long-running TUIs to the PyPy fast path (`require_ait_python_fast`); two TUIs were deliberately excluded — `aitask_monitor.sh` and `aitask_minimonitor.sh` — under the assumption that their dominant cost is `fork+exec(tmux)` (OS-level, which PyPy cannot accelerate).

This task **empirically tests** that assumption. The deliverable is binary:

- **(a) KEEP** — if PyPy yields ≥ 10-15% wall-clock improvement on a representative monitor workload, swap line 12 of both launchers to `require_ait_python_fast` and document the win.
- **(b) REVERT** — otherwise, leave the launchers on `require_ait_python`, document the negative result in `aidocs/python_tui_performance.md`, and add a CLAUDE.md note anchoring the assumption empirically (so future agents do not re-attempt this without t719's tmux control-mode refactor in hand).

Pre-flight findings already established before entering plan mode:

- PyPy 3.11.15 is installed at `~/.aitask/pypy_venv/bin/python` (so we can measure).
- Both `aitask_monitor.sh` and `aitask_minimonitor.sh` have the identical literal `PYTHON="$(require_ait_python)"` at line 12 — confirmed.
- Parent task `aitasks/t718_pypy_optional_runtime_for_tui_perf.md` is still pending (t718_4, t718_5 not archived). There is **no `aiplans/p718.md` parent plan file** — only child plans exist. The task description's reference to "parent t718 plan" must be re-interpreted as `aidocs/python_tui_performance.md` (the canonical perf doc that p718_2 already updates) plus a CLAUDE.md note. This is a clarification of the original task wording, not a scope change.

## Methodology

The original task description suggested "launch monitor, page through 50 sessions, measure total elapsed time and tmux IPC count" — but interactive paging is non-reproducible. Replace with a more rigorous three-part measurement:

### Part 1 — Hot-path microbenchmark (primary signal)

Build a one-off, **uncommitted** benchmark script `/tmp/bench_capture_all_async.py` that:

1. Imports `tmux_monitor` from `.aitask-scripts/monitor/`.
2. Instantiates `TmuxMonitor(session=<bench_session>, project_root=<repo_root>)` against an isolated benchmark tmux session (NOT the user's `aitasks` session — see Risk note).
3. Warms up with 3 ticks (skip these in the reported result; ensures asyncio/PyPy machinery is hot).
4. Runs `asyncio.run(monitor.capture_all_async())` in a loop for `N=100` iterations.
5. Reports: wall time total, per-tick median, per-tick p95, panes-per-tick.

This isolates the exact function called every 3 seconds in `monitor_app.py` — the hot path identified in `aidocs/python_tui_performance.md:30-32`. Microbenchmarking this directly answers "does PyPy help?" without TUI/Textual noise.

### Part 2 — Cold-start measurement (secondary signal)

PyPy has a known ~150-300 ms warmup penalty (per `aidocs/python_tui_performance.md:117`). For a TUI the user opens many times per day, cold-start matters. Time `python -c "import sys; sys.path.insert(0, '.aitask-scripts/monitor'); import monitor_app"` (avoids actually launching the TUI but pays the import + Textual-load cost) under each interpreter, 5 reps, report median.

If cold-start regression > the hot-path win on a typical session (say, 30 ticks per launch), PyPy is net-negative even if Part 1 shows a per-tick gain.

### Part 3 — System-call profile (sanity check on the assumption)

Run `strace -c -e fork,execve,clone3 -p <monitor_pid>` for ~15 seconds against a real monitor session (still in the benchmark tmux session) to confirm the "fork+exec dominates" claim is true on this machine in 2026. Report the per-second fork/execve counts. If somehow fork/exec is NOT dominant (e.g., asyncio overhead has bloated), the assumption itself was wrong and PyPy could matter more than expected.

### Workload

- Benchmark tmux session: created fresh by the plan execution (separate name like `pypy_bench_$$` so it cannot collide with `aitasks`).
- Pane count: run the measurement at **3 pane-count points**: 3 panes (sparse), 8 panes (typical), 15 panes (heavy). This bounds the answer across realistic usage.
- Pane content: each pane just runs `bash` with a small banner so `capture-pane` has something non-trivial to return.

### Decision rule (binary, written upfront)

Compute the per-tick wall-time delta:

```
delta% = (CPython_median_per_tick - PyPy_median_per_tick) / CPython_median_per_tick × 100
```

- **KEEP** if `delta% ≥ 10` at the 8-pane workload AND PyPy cold-start regression doesn't exceed the per-launch savings over 30 ticks.
- **REVERT** otherwise.

The 10% threshold is the lower bound of the task description's "10-15%" range. Tie-breaking goes to REVERT (status quo) since the swap adds a small distribution surface — every TUI that opts into the fast path must also be smoke-tested on systems without PyPy installed.

### Risk note (per CLAUDE.md memory)

Per the user's `feedback_tmux_stress_tasks_outside_tmux` memory, this task involves running monitor against a benchmark tmux session. The benchmark session has a unique name (`pypy_bench_$$`) and is killed in the cleanup step — it does NOT touch the user's `aitasks` session. The monitor instances launched for Part 3 attach to the bench session and quit after ~15 s. There is no destructive tmux operation; this can safely run inside the user's main shell without `kill-server` risk.

## Key Files to Modify (or revert)

- `.aitask-scripts/aitask_monitor.sh` line 12: `PYTHON="$(require_ait_python)"` → `PYTHON="$(require_ait_python_fast)"` (conditional on decision)
- `.aitask-scripts/aitask_minimonitor.sh` line 12: same edit (conditional)
- `aidocs/python_tui_performance.md`: append measurement results table at the end (regardless of decision)
- `CLAUDE.md` "Project-Specific Notes": add a one-line entry only if REVERT (anchors the negative result so future plans don't re-litigate it)

## Out of scope

- The t719 tmux control-mode refactor (`tmux -C`). This task is the 2-line swap + measurement only, per the task description's "Do not let this task expand into the t719 tmux control-mode refactor".
- Modifying `aitask_stats_tui.sh` (it's CPython-pinned due to `plotext`, per `aidocs/python_tui_performance.md:109`).
- Modifying `aitask_diffviewer.sh` (transitional per CLAUDE.md).

## Reference files for patterns

- `aiplans/archived/p718/p718_2_*.md` — same 1-line edit pattern; precedent for how to land/document the swap.
- `aidocs/python_tui_performance.md` — perf doc that should hold the results table; section to extend is "Per-TUI Bottleneck Classification".
- `.aitask-scripts/monitor/tmux_monitor.py:570-583` — `capture_all_async()`, the function being microbenchmarked.
- `.aitask-scripts/lib/python_resolve.sh` — defines `require_ait_python_fast` (line 130) and `require_ait_pypy` (line 123). No changes here.

## Implementation steps

### 1. Pre-flight verification

```bash
# Confirm PyPy is installed and runnable
~/.aitask/pypy_venv/bin/python -c "import sys; print(sys.implementation.name, sys.version)"
# Expected: pypy 3.11.x

# Confirm baseline launchers are unmodified
git diff -- .aitask-scripts/aitask_monitor.sh .aitask-scripts/aitask_minimonitor.sh
# Expected: empty

# Confirm both target lines match
awk 'NR==12' .aitask-scripts/aitask_monitor.sh .aitask-scripts/aitask_minimonitor.sh
# Expected: both lines == PYTHON="$(require_ait_python)"
```

### 2. Set up isolated benchmark tmux session

```bash
BENCH_SESSION="pypy_bench_$$"
tmux new-session -d -s "$BENCH_SESSION" -x 200 -y 50 "bash -i"
for i in $(seq 1 2); do
  tmux split-window -t "$BENCH_SESSION:0" "bash -c 'echo pane-$i; exec bash -i'"
done
tmux select-layout -t "$BENCH_SESSION:0" tiled
# Verify
tmux list-panes -t "$BENCH_SESSION" | wc -l   # expect 3
```

Repeat for the 8-pane and 15-pane points (separate sessions or different windows).

### 3. Build the microbenchmark script

Write `/tmp/bench_capture_all_async.py` (uncommitted, deleted in cleanup). Structure:

```python
import argparse, asyncio, statistics, sys, time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--session", required=True)
parser.add_argument("--iterations", type=int, default=100)
parser.add_argument("--warmup", type=int, default=3)
args = parser.parse_args()

repo = Path(__file__).resolve().parents[?]  # adjust to repo root
sys.path.insert(0, str(repo / ".aitask-scripts" / "monitor"))
from tmux_monitor import TmuxMonitor

monitor = TmuxMonitor(session=args.session, project_root=repo)

async def run():
    # warmup
    for _ in range(args.warmup):
        await monitor.capture_all_async()
    # measure
    samples = []
    for _ in range(args.iterations):
        t0 = time.perf_counter()
        snaps = await monitor.capture_all_async()
        samples.append((time.perf_counter() - t0) * 1000)  # ms
    return samples, snaps

samples, snaps = asyncio.run(run())
print(f"impl={sys.implementation.name} panes={len(snaps)} n={len(samples)} "
      f"median={statistics.median(samples):.2f}ms "
      f"p95={statistics.quantiles(samples, n=20)[-1]:.2f}ms "
      f"total={sum(samples):.0f}ms")
```

(Final script will resolve `parents[?]` correctly and check `TmuxMonitor`'s actual constructor signature before running — both verified during implementation.)

### 4. Run Part 1 (hot-path microbenchmark)

For each pane count (3, 8, 15) and each interpreter, run 3 reps and take the median of medians:

```bash
# CPython baseline
for rep in 1 2 3; do
  ~/.aitask/venv/bin/python /tmp/bench_capture_all_async.py --session "$BENCH_SESSION" --iterations 100
done

# PyPy
for rep in 1 2 3; do
  ~/.aitask/pypy_venv/bin/python /tmp/bench_capture_all_async.py --session "$BENCH_SESSION" --iterations 100
done
```

Record results in a markdown table (kept in the plan + later mirrored to `aidocs/python_tui_performance.md`).

### 5. Run Part 2 (cold-start)

```bash
# Each repeated 5 times via `time` or `hyperfine` if available
~/.aitask/venv/bin/python -c "
import sys; sys.path.insert(0, '.aitask-scripts/monitor')
import monitor_app
"
~/.aitask/pypy_venv/bin/python -c "
import sys; sys.path.insert(0, '.aitask-scripts/monitor')
import monitor_app
"
```

Compute regression delta in ms.

### 6. Run Part 3 (strace sanity check, Linux only)

```bash
# Launch a monitor instance against bench session in background
AIT_USE_PYPY=0 ./.aitask-scripts/aitask_monitor.sh --session "$BENCH_SESSION" &
mon_pid=$!
sleep 2  # let it initialize
strace -c -e fork,execve,clone3 -p "$mon_pid" &
strace_pid=$!
sleep 15
kill "$strace_pid"
kill "$mon_pid"
```

Confirm the per-tick fork+execve count matches `~N panes × ticks-in-15s` (i.e., fork/exec is the per-tick cost, validating the bottleneck assumption).

### 7. Decide and apply the edit (or not)

Apply the decision rule from the Methodology section.

**If KEEP:**

```bash
# Edit both files
# Line 12: PYTHON="$(require_ait_python)" → PYTHON="$(require_ait_python_fast)"
```

Followed by:

```bash
shellcheck .aitask-scripts/aitask_monitor.sh .aitask-scripts/aitask_minimonitor.sh
git diff --stat   # expect 2 files, 1 ins + 1 del each
```

Smoke test both launchers in a fresh shell (without and with PyPy active).

**If REVERT:**

No code edits to launchers (they were never modified — the decision is made BEFORE editing). Verify:

```bash
git diff -- .aitask-scripts/aitask_monitor.sh .aitask-scripts/aitask_minimonitor.sh
# Expected: empty
```

### 8. Documentation (always)

**Always update `aidocs/python_tui_performance.md`** — append a new section "## t718_5 Empirical Verification (2026-05-17)" containing:

- Workload description (pane counts, iterations, machine info)
- Results table:

  | Pane count | CPython per-tick median | PyPy per-tick median | Delta % | Cold-start delta |
  |---|---|---|---|---|
  | 3 | … | … | … | … |
  | 8 | … | … | … | … |
  | 15 | … | … | … | … |

- The strace fork+exec rate
- The decision (KEEP / REVERT) and rationale

**If REVERT, also add to CLAUDE.md "Project-Specific Notes":**

A one-line entry like:

> - **monitor/minimonitor stay on CPython.** Empirically verified by t718_5 (2026-05-17): PyPy yielded \<X%\> per-tick win — below the 10% threshold — because `fork+exec(tmux)` dominates per `aidocs/python_tui_performance.md`. Do not re-litigate without t719's tmux control-mode refactor in hand.

### 9. Cleanup

```bash
tmux kill-session -t "$BENCH_SESSION" 2>/dev/null || true
rm -f /tmp/bench_capture_all_async.py
```

### 10. Step 9 — Post-Implementation

Standard child-task archival per `task-workflow/SKILL.md` Step 9:

- Commit code changes (if KEEP: 2 launcher files; if REVERT: only `aidocs/python_tui_performance.md` + `CLAUDE.md`)
- Commit plan file separately via `./ait git`
- Run archive script for child task `718_5`
- Verify `t718_4` (manual verification) is still the only pending sibling

## Verification

- `shellcheck` clean on both launchers (only relevant on KEEP branch — they're untouched on REVERT).
- `aidocs/python_tui_performance.md` contains the new section with a results table and the decision.
- On KEEP: `./ait monitor --session aitasks` launches and renders normally under both CPython and PyPy.
- On REVERT: `git diff --stat` against base shows changes only in `aidocs/python_tui_performance.md` and `CLAUDE.md` — not in the two launcher scripts.
- Benchmark tmux session `pypy_bench_$$` is gone (`tmux ls` doesn't list it).
- `/tmp/bench_capture_all_async.py` is deleted.

## Notes for sibling tasks

- **t718_4 (manual verification)** — when picked, its checklist already enumerates the 6 fast-path TUIs from t718_2. If this task lands as KEEP, the checklist should be extended to include `monitor` and `minimonitor` smoke tests under PyPy. If REVERT, no change to t718_4's checklist.
- **t718 parent** — once t718_4 and this task are archived, t718 can be archived too (its `children_to_implement` should drop to empty).
- **t719 (tmux control mode)** — independent of this task's outcome. Even if PyPy were a small win here, t719's potential 5-20× refresh speedup remains the long-term win for monitor/minimonitor.

## Post-Review Changes

### Change Request 1 (2026-05-17 11:00)

- **Requested by user:** "task t719 is already mostly implemented how do you explain the slow down with pypy?" — call-out that t719's `tmux -C` control-mode refactor was already landed, so the original "fork+exec dominates" assumption embedded in the plan and the first round of measurements no longer reflects the real hot path.
- **Investigation:** Confirmed `aitasks/archived/t719/t719_2_hot_path_integration.md` exists; `_tmux_async` in `tmux_monitor.py:246` routes through `TmuxControlBackend` when the backend is alive; `monitor_app.py:642` and `minimonitor_app.py:241` both start the control client at app boot. The benchmark I ran first never called `await monitor.start_control_client()`, so `_backend` stayed `None` and `_tmux_async` fell through to the legacy `_run_tmux_async` (fork+exec) path. My initial measurement was of the obsolete fallback path.
- **Changes made:**
  1. Rewrote `/tmp/bench_capture_all_async.py` to import `tmux_monitor` as `monitor.tmux_monitor` (fixes its relative import `from .tmux_control import …`), call `await monitor.start_control_client()`, verify `backend=control` is alive, and report which path the run exercised. Added a `--no-control` flag for the comparison.
  2. Re-ran the full pane-count sweep (3/8/15) on the control-mode path with extended warmup (500 PyPy warmup iterations vs 50 CPython, since PyPy needs many more samples before JIT specializes) and 500 measurement iterations × 3 reps.
  3. Replaced the "fork+exec dominates" framing in `aidocs/python_tui_performance.md` with a two-table writeup (fallback path + control-mode path) and a corrected rationale section.
  4. Rewrote the `CLAUDE.md` "Project-Specific Notes" entry to drop the obsolete "until t719 lands" caveat and instead reference t719_4 (pipe-pane push, still pending) as the next point at which the verdict should be re-evaluated.
- **Files affected:** `/tmp/bench_capture_all_async.py` (uncommitted), `aidocs/python_tui_performance.md`, `CLAUDE.md`.
- **Final verdict (unchanged):** REVERT. PyPy loses on both the legacy fallback path AND the post-t719_2 control-mode path, for different reasons.

## Final Implementation Notes

- **Actual work done:** Two-phase measurement against PyPy 7.3.21 / Python 3.11.15 vs CPython 3.14.4 on this Linux machine. Set up three isolated benchmark tmux sessions (`pypy_bench_<pid>_{3,8,15}`) with 3/8/15 bash panes, built `/tmp/bench_capture_all_async.py` (uncommitted), and microbenchmarked `TmuxMonitor.capture_all_async()` with `multi_session=False`. **Phase 1** (initial, incorrect — measured the legacy fork+exec fallback because the benchmark never started the control client): N=100 iter, 20 warmup, 3 reps. **Phase 2** (corrected, after user pointed out t719_2 already landed): re-ran the benchmark with `await monitor.start_control_client()` and verified `backend=control` alive; used N=500 iter and 500-iter PyPy warmup / 50-iter CPython warmup to fully prime PyPy's JIT, 3 reps. Also measured `import monitor_app` cold-start (5 reps per interpreter).

  Final result — control-mode path (the path monitor actually takes today):

  | Panes | CPython median | PyPy median | Ratio |
  |-------|---------------:|------------:|------:|
  | 3     | 0.37 ms        | 0.65 ms     | PyPy 76% slower |
  | 8     | 0.62 ms        | 1.18 ms     | PyPy 90% slower |
  | 15    | 1.03 ms        | 1.01 ms     | ~equal (within noise) |

  Reference — legacy fallback path (pre-t719_2; included for comparison since the benchmark exercises this path when `--no-control` is set):

  | Panes | CPython median | PyPy median | Ratio |
  |-------|---------------:|------------:|------:|
  | 3     | 2.75 ms        | 8.90 ms     | PyPy 3.2× slower |
  | 8     | 3.47 ms        | 19.17 ms    | PyPy 5.5× slower |
  | 15    | 4.61 ms        | 34.14 ms    | PyPy 7.4× slower |

  Cold-start: CPython 159 ms vs PyPy 325 ms (~2× slower).

  Verdict: **REVERT**. No launcher edits made; `git diff` against base shows zero change to `.aitask-scripts/aitask_monitor.sh` and `.aitask-scripts/aitask_minimonitor.sh`. Documentation updates: `aidocs/python_tui_performance.md` has a new "t718_5 Empirical Verification" section with both result tables and corrected rationale; `CLAUDE.md` "Project-Specific Notes" has a new bullet documenting the negative result and the conditions under which it should be re-evaluated.

- **Deviations from plan:** Four:
  1. **Part 3 (strace sanity check) was skipped** — `strace` is not installed on this machine. Part 1's microbenchmark measures end-to-end per-tick wall time directly, which is the actual KEEP/REVERT input; the strace check would have only verified the *root cause* of the slowness in the legacy path, not changed the decision.
  2. **`/usr/bin/time` is not present on this Arch system** — used `date +%s.%N` arithmetic for cold-start timing instead. Functionally equivalent; reported in ms.
  3. **The decision rule's secondary clause ("PyPy cold-start regression doesn't exceed per-launch savings over 30 ticks") was moot** — there are no per-launch savings to compare against; PyPy is slower on both the per-tick path AND cold-start.
  4. **The plan's framing ("fork+exec dominates, so PyPy can't help") was based on an obsolete view of the codebase.** t719_2 had already eliminated per-tick fork+exec from the production hot path before this task was picked. The initial measurement had to be redone after the user pointed this out. The corrected measurement (control-mode path) shows PyPy still loses, but for a different reason: per-coroutine + cross-thread overhead. The plan's Context section underestimated how much of t719 was already done — a planning-time miss documented here so future tasks of this class (benchmarking a path that may have already been refactored) explicitly verify the path under test.

- **Issues encountered:**
  1. `tmux split-window -t "=$S:0"` failed silently — sessions created by `new-session -d -s NAME "command"` index their first window as `1`, not `0`. Switched to bare `-t "$S"` (active window) and rebuilt sessions.
  2. **Most important methodology bug**: the initial benchmark instantiated `TmuxMonitor` but never called `await monitor.start_control_client()`, so `_backend` stayed `None` and the benchmark exercised the legacy `_run_tmux_async` fallback (fork+exec per pane). This was only caught when the user flagged "t719 is already mostly implemented". Fix: explicitly start the control client in the bench script and assert `monitor._backend.is_alive` before measuring. Lesson: when benchmarking a code path that has an alternate implementation behind a runtime switch (here: backend vs fallback), always assert which path is actually exercised before believing the numbers.
  3. PyPy JIT under-warmup: 20 warmup iterations was not enough for PyPy on the control-mode path. Increased to 500 PyPy warmup iterations for the final sweep; PyPy median per-tick dropped from ~2 ms to ~1.2 ms post-warmup, but stayed slower than CPython at every realistic pane count.

- **Key decisions:**
  1. **Use `multi_session=False`** when instantiating `TmuxMonitor` for the bench. Scopes `discover_panes_async()` to the bench session and prevents accidental inclusion of the user's `aitasks` session panes, which would skew pane counts.
  2. **Three pane-count points (3/8/15)** rather than one "typical" number. The control-mode slowdown ratio *narrows* with pane count (76% → 90% → ~equal), which surfaces the per-tick fixed-overhead nature of PyPy's penalty here and motivates the "re-evaluate after t719_4" guidance.
  3. **No code edits to launchers** even temporarily — the plan was written so the decision is made *before* editing. The launchers remain unmodified across the entire workflow.
  4. **Document both paths**, not just the production path. The legacy fallback path numbers stay useful because (a) they describe what happens when the control client fails to start (which `_tmux_async` falls back to), and (b) they validate the historical "fork+exec dominates" framing for the pre-t719 codebase.
  5. **The CLAUDE.md note explicitly names t719_4 as the next re-evaluation trigger** (not t719 in general), because t719_2 has already landed and PyPy still loses; only a further reshaping of the per-tick work (e.g., pipe-pane push) could plausibly flip the verdict.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t718_4 (manual verification)** — no checklist change required. The fast-path TUI list ratified there is unchanged.
  - **t718 parent** — after t718_4 archives, t718's `children_to_implement` drops to empty and it can be archived too.
  - **t719_3 (adaptive polling)** — if/when it archives, the per-tick *frequency* changes, not the per-tick *cost*; this benchmark's per-tick numbers stay relevant. No re-measurement needed for that child alone.
  - **t719_4 (pipe-pane push)** — when it archives, **re-run this benchmark**. Push-based delivery shifts work from "send a command, await a frame" toward "read and parse pushed frames", which is the workload class where PyPy traditionally helps. The current REVERT verdict may flip there. Reference this plan's bench script structure.
  - **t719_5 (manual verification of monitor tmux control)** — independent of this task.
  - **t719_6 (architecture evaluation)** — should cite this task's control-mode numbers as the post-t719_2 baseline against which any further architectural change should compare.
  - **Future long-running TUIs** should call `require_ait_python_fast` from the start *only* if their hot path is Python-bound (Textual rendering, frontmatter parsing, large data transforms). TUIs whose hot path is per-tick coordinated subprocess/IPC work — where the per-call overhead dominates — should stay on `require_ait_python`. This task is the empirical anchor for that rule.
