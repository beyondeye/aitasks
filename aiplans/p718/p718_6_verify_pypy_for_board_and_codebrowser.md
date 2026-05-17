---
Task: t718_6_verify_pypy_for_board_and_codebrowser.md
Parent Task: aitasks/t718_pypy_optional_runtime_for_tui_perf.md
Sibling Tasks: aitasks/t718/t718_4_manual_verification_pypy_optional_runtime_for_tui_perf.md
Archived Sibling Plans: aiplans/archived/p718/p718_1_pypy_infrastructure_setup_resolver.md, aiplans/archived/p718/p718_2_wire_long_running_tuis_to_fast_path.md, aiplans/archived/p718/p718_3_documentation_pypy_runtime.md, aiplans/archived/p718/p718_5_verify_pypy_for_monitor_minimonitor.md
Base branch: main
plan_verified: []
---

# Plan: t718_6 — Verify PyPy for board / codebrowser

## Context

Sibling t718_2 wired six long-running Textual TUIs to the PyPy fast path
(`require_ait_python_fast`) on the *theoretical* grounds that PyPy's JIT
"often delivers 2-5× on Textual workloads" (claim in
`aidocs/python_tui_performance.md`). That claim was never measured
empirically against the actual board / codebrowser code paths.

Then t718_5 measured monitor/minimonitor — also "PyPy-friendly" on paper
(asyncio-heavy with low per-tick Python work) — and found PyPy is
**dramatically slower** on both the legacy fork+exec fallback path AND the
post-t719_2 tmux control-mode path. Verdict: REVERT.

This task applies the same skepticism to the **two largest Textual
surfaces still on the fast path** — `ait board` (`KanbanApp`, 5176 LOC)
and `ait codebrowser` (`CodeBrowserApp`, 1504 LOC main file + helpers
under `.aitask-scripts/codebrowser/`). Decision is binary per TUI; settings
/ brainstorm / stats / syncer are intentionally left out of scope.

## Decision rule (binary, written upfront)

For each TUI independently, compute the per-workload wall-time delta:

```
delta% = (CPython_median - PyPy_median) / CPython_median × 100
```

- **KEEP** if `delta% ≥ 10` on the Pilot workload AND PyPy cold-start
  regression (~150-300 ms warmup) does not exceed the per-launch savings
  over a typical session (board: ~30-60 s; codebrowser: ~2-5 min).
- **REVERT** otherwise. Edit line 12 of the relevant launcher back to
  `require_ait_python` and document the negative result.

Tie-breaking goes to **REVERT** (status quo before t718_2 was CPython).
Per-TUI verdicts are independent — `mixed` (one KEEP, one REVERT) is a
valid outcome.

## Methodology

### Part 1 — Pilot-driven workload (primary signal)

Build one **uncommitted** benchmark script per TUI under `/tmp/`. Each
script:

1. Imports the App class (`KanbanApp` from `.aitask-scripts/board/aitask_board.py`
   or `CodeBrowserApp` from `.aitask-scripts/codebrowser/codebrowser_app.py`),
   patching `sys.path` to include the parent dir so internal relative
   imports resolve.
2. Runs `App().run_test(size=(160, 48))` in an `async with … as pilot`
   block (the exact pattern in `tests/test_board_view_filter.py:76`).
3. **Warm-up:** runs the workload twice and discards both timings (PyPy
   needs many iterations to JIT — t718_5 found 500 warmup iterations
   necessary for asyncio-heavy code, but Pilot-driven Textual work has
   far more diverse code paths per tick; 2-rep warmup with N=5
   measurement reps is the same shape as t718_5's *measurement* loop and
   should suffice for these UI-class workloads).
4. **Measurement:** runs the workload 5 times, records each via
   `time.perf_counter()` around the `async with` block (i.e. measures
   startup + workload + teardown).
5. Reports per-rep wall times in ms, plus median and p95.

**Workloads:**

- **Board (`KanbanApp`):**
  ```python
  await pilot.pause()                           # let mount settle
  for _ in range(20): await pilot.press("down") # cycle through tasks
  await pilot.press("a")                        # toggle "show all"
  await pilot.press("i")                        # toggle "implementing only"
  await pilot.press("g")                        # toggle "git/show archived"
  await pilot.press("a")                        # back to default
  await pilot.press("r")                        # refresh board
  await pilot.pause()                           # let final refresh settle
  ```
  Exercises the on-disk task-file scan + frontmatter parsing in
  `refresh_board()` (`aitask_board.py:3401`) plus the BINDINGS handlers
  at `aitask_board.py:3278`. **Avoid `enter` / `space` / `n`** — those
  push ModalScreens which would freeze Pilot.

- **Codebrowser (`CodeBrowserApp`):**
  Launch with the `--focus` CLI arg pointing at a large file
  (`.aitask-scripts/brainstorm/brainstorm_app.py` ~5200 LOC). This
  short-circuits the file-tree pane and opens the viewer directly
  (parsed by `_parse_focus_value()` at `codebrowser_app.py:454`).
  ```python
  await pilot.pause()
  for _ in range(10): await pilot.press("pagedown")
  for _ in range(10): await pilot.press("pageup")
  await pilot.press("end")                      # jump to bottom
  await pilot.press("home")                     # back to top
  await pilot.pause()
  ```
  Exercises the syntax-highlighter, viewport scroll, and Tree-sitter /
  Rich rendering paths in `code_viewer.py:40-48` and below.

### Part 2 — Cold-start measurement (secondary signal)

Per-interpreter, 5 reps each, median reported:

```bash
# Board cold-start
~/.aitask/venv/bin/python -c "import sys; sys.path.insert(0, '.aitask-scripts/board'); import aitask_board"
~/.aitask/pypy_venv/bin/python -c "import sys; sys.path.insert(0, '.aitask-scripts/board'); import aitask_board"

# Codebrowser cold-start
~/.aitask/venv/bin/python -c "import sys; sys.path.insert(0, '.aitask-scripts/codebrowser'); import codebrowser_app"
~/.aitask/pypy_venv/bin/python -c "import sys; sys.path.insert(0, '.aitask-scripts/codebrowser'); import codebrowser_app"
```

Time each invocation with `date +%s.%N` arithmetic (t718_5 confirmed
`/usr/bin/time` is absent on this Arch system). Report ms.

### Part 3 — Verify which path is exercised (methodology guardrail)

Per t718_5's methodology lesson — when benchmarking a code path that
has an alternate behind a runtime switch, verify the path under test.
**Neither board nor codebrowser has such a switch** (no
backend/fallback), so this is reduced to a sanity check:

- In each bench script, after `App.run_test()` enters, log
  `sys.implementation.name` and `sys.version` so the reported numbers
  unambiguously identify which interpreter ran them.
- Verify the workload finished without raising (Pilot will hang on a
  modal — if the script doesn't finish in reasonable time, the workload
  is wrong and the numbers are invalid).

## Key Files to Modify (conditional)

- `.aitask-scripts/aitask_board.sh` line 12 — REVERT only:
  `require_ait_python_fast` → `require_ait_python`
- `.aitask-scripts/aitask_codebrowser.sh` line 12 — REVERT only, same edit
- `aidocs/python_tui_performance.md` — **always** append a "t718_6
  Empirical Verification" section (mirrors the t718_5 section format),
  one results table per TUI plus cold-start row, with per-TUI verdict
- `aidocs/python_tui_performance.md` "Dual-venv, opt-in" row — update
  the TUI enumeration if any REVERT
- `CLAUDE.md` "Project-Specific Notes" — REVERT only: add a one-line
  entry per reverted TUI anchoring the empirical basis (in the style of
  the t718_5 monitor/minimonitor entry already present)

## Reference Files for Patterns

- `aiplans/archived/p718/p718_5_verify_pypy_for_monitor_minimonitor.md` —
  sibling task, same overall pattern. **Methodology lesson** (per its
  Post-Review Changes): verify which path is exercised before believing
  numbers. Also: PyPy needs many warmup iterations to JIT-specialize.
- `aiplans/archived/p718/p718_2_wire_long_running_tuis_to_fast_path.md` —
  the task that originally wired both launchers to the fast path. Its
  edit was a single-line diff per launcher.
- `aidocs/python_tui_performance.md` — perf doc that hosts the results
  section. The "t718_5 Empirical Verification" section is the format to
  mirror.
- `tests/test_board_view_filter.py:76` — canonical Pilot pattern
  (`app.run_test(size=(160, 48))` context manager + `await pilot.pause()`
  for settle).
- `.aitask-scripts/board/aitask_board.py:3091` — `KanbanApp` class.
- `.aitask-scripts/board/aitask_board.py:3278` — BINDINGS table (lists
  the keys safe to drive from Pilot without entering a modal).
- `.aitask-scripts/codebrowser/codebrowser_app.py:291` — `CodeBrowserApp`
  class.
- `.aitask-scripts/codebrowser/codebrowser_app.py:454` —
  `_parse_focus_value()`, the `--focus` short-circuit.
- `.aitask-scripts/codebrowser/code_viewer.py:40-48` — viewer BINDINGS.

## Implementation Steps

### 1. Pre-flight verification

```bash
# PyPy installed and runnable
~/.aitask/pypy_venv/bin/python -c "import sys; print(sys.implementation.name, sys.version)"
# Expected: pypy 3.11.x

# Baseline launchers unmodified
git diff -- .aitask-scripts/aitask_board.sh .aitask-scripts/aitask_codebrowser.sh
# Expected: empty

# Both target lines match (line 12)
awk 'NR==12' .aitask-scripts/aitask_board.sh .aitask-scripts/aitask_codebrowser.sh
# Expected: both lines == PYTHON="$(require_ait_python_fast)"
```

### 2. Build the Pilot bench scripts

Write `/tmp/bench_board_pilot.py` and `/tmp/bench_codebrowser_pilot.py`
following the structure described in Methodology Part 1. Both scripts:

- Take `--reps N` (default 5), `--warmup K` (default 2).
- Use `time.perf_counter()` around the `async with app.run_test(size=(160, 48)) as pilot:` block.
- Print one line per rep + a summary line: `impl=<pypy|cpython> reps=N median=Xms p95=Yms`.

The codebrowser script must pass `--focus
.aitask-scripts/brainstorm/brainstorm_app.py` to the `CodeBrowserApp`
constructor (or via `sys.argv` patch — check whichever the app supports
without going through the bash launcher).

### 3. Run Part 1 (Pilot workload)

For each TUI × each interpreter × 3 reps of the whole script (the script
itself does 5 measurement passes; we run the script 3 times to capture
between-run variance):

```bash
# Board, CPython
for r in 1 2 3; do ~/.aitask/venv/bin/python /tmp/bench_board_pilot.py; done
# Board, PyPy
for r in 1 2 3; do ~/.aitask/pypy_venv/bin/python /tmp/bench_board_pilot.py; done

# Codebrowser, CPython
for r in 1 2 3; do ~/.aitask/venv/bin/python /tmp/bench_codebrowser_pilot.py; done
# Codebrowser, PyPy
for r in 1 2 3; do ~/.aitask/pypy_venv/bin/python /tmp/bench_codebrowser_pilot.py; done
```

Record the median-of-medians per cell.

### 4. Run Part 2 (cold-start)

5 reps per interpreter × per TUI using `date +%s.%N` arithmetic. Report
median ms per cell.

### 5. Decide per TUI

Apply the decision rule from above. Possibilities:

- **Both KEEP** → no launcher edits, document the wins in
  `aidocs/python_tui_performance.md`.
- **Both REVERT** → revert both launchers; document the negative result
  + update CLAUDE.md.
- **Mixed** → revert only the loser; document both outcomes per-TUI.

### 6. Apply edits (REVERT branch) or document the wins (KEEP branch)

REVERT edit pattern (per losing TUI):

```diff
-PYTHON="$(require_ait_python_fast)"
+PYTHON="$(require_ait_python)"
```

### 7. Documentation (always)

Append to `aidocs/python_tui_performance.md`:

```markdown
## t718_6 Empirical Verification (2026-05-17)

Workload: Textual `App.run_test()` Pilot-driven scripted keystrokes
against KanbanApp / CodeBrowserApp. CPython 3.X.X vs PyPy 7.3.21 / Python
3.11.15. <Machine info>.

### Board (KanbanApp)

| Metric | CPython median | PyPy median | Delta % |
|---|---:|---:|---:|
| Pilot workload | … | … | … |
| Cold-start (import) | … | … | … |

**Verdict: KEEP / REVERT** — <one-sentence rationale>

### Codebrowser (CodeBrowserApp)

| Metric | CPython median | PyPy median | Delta % |
|---|---:|---:|---:|
| Pilot workload | … | … | … |
| Cold-start (import) | … | … | … |

**Verdict: KEEP / REVERT** — <one-sentence rationale>
```

On REVERT (per TUI), extend the existing CLAUDE.md "Project-Specific
Notes" PyPy bullet (or add a new bullet) in the style of the t718_5
monitor/minimonitor entry already present.

### 8. Update fast-path TUI list if any REVERT

`aidocs/python_tui_performance.md` "Dual-venv, opt-in" row enumerates the
fast-path TUIs. If board or codebrowser drops off, edit that
enumeration. Per CLAUDE.md "Documentation Writing", state the current
state only — no "earlier versions said…" prose.

### 9. Cleanup

```bash
rm -f /tmp/bench_board_pilot.py /tmp/bench_codebrowser_pilot.py
```

### 10. Step 9 — Post-Implementation

Standard child-task archival per `task-workflow/SKILL.md` Step 9:

- **If KEEP both:** commit `aidocs/python_tui_performance.md` only.
- **If REVERT any:** commit launcher edit(s) + `aidocs/...` + `CLAUDE.md`.
- Commit plan file separately via `./ait git`.
- Run archive script for child task `718_6`.
- Sibling t718_4 (manual verification) remains pending after this
  archives — that is the final child blocking parent t718 archival.

## Verification

- On REVERT: `git diff` against base shows the expected single-line
  revert in the affected launcher(s) and nothing else in `.aitask-scripts/`.
- On KEEP: `git diff -- .aitask-scripts/` is empty.
- `shellcheck` clean on any modified launcher.
- On REVERT: `AIT_USE_PYPY=1 ./ait <tui>` falls back to CPython (because
  the launcher now uses `require_ait_python`, which ignores
  `AIT_USE_PYPY`). On KEEP: `AIT_USE_PYPY=0 ./ait <tui>` still launches
  normally; `AIT_USE_PYPY=1 ./ait <tui>` launches under PyPy.
- `aidocs/python_tui_performance.md` contains the new "t718_6 Empirical
  Verification" section with one results table per TUI and per-TUI
  verdict.
- `/tmp/bench_*_pilot.py` deleted.

## Notes for sibling tasks

- **t718_4 (manual verification)** — if either board or codebrowser
  REVERTs, the checklist's "fast-path TUI list" should be updated
  accordingly before t718_4 is picked. If both KEEP, no change required.
- **t718 parent** — once t718_4 archives (and this task is already
  archived), t718's `children_to_implement` drops to empty and the
  parent can be archived.
- **Settings / brainstorm / stats / syncer (intentionally out of scope)**
  — if both board and codebrowser REVERT, follow-up tasks should
  consider auditing the rest of the fast-path TUI list. If both KEEP,
  the others can be presumed to track until a counter-signal arises.
- **Future long-running TUIs** — per t718_5's "Notes for sibling
  tasks", call `require_ait_python_fast` from the start only when the
  hot path is Python-bound (Textual rendering, frontmatter parsing,
  large data transforms). This task's verdict adds the further data
  point for the rule.
