---
priority: medium
effort: high
depends: []
issue_type: performance
status: Ready
labels: [test, tui, board, performance]
gates: [risk_evaluated]
folded_tasks: [1346, 1352]
anchor: 1111
created_at: 2026-07-31 07:41
updated_at: 2026-07-31 07:41
---

## Problem

`bash tests/run_all_python_tests.sh` takes ~12 minutes (746s for ~2900 tests,
per the run recorded in t1346). That cost sits on the critical path of every
task's Step 8b full-suite run, and it **grows every week** — see the root cause
below, which scales with the number of files in `aitasks/`.

## Measured evidence

All figures below were measured on this checkout (24 cores, `~/.aitask/venv`
Python 3.14), not estimated.

### The cost is extremely concentrated

Each of the 174 `tests/test_*.py` modules was timed individually
(`python -m unittest discover -s tests -p <file>`); the sum is 688s (the real
aggregate is 746s — the difference is per-file interpreter startup vs. one
shared process).

```
  164.58  test_board_bytrail_view.py
  123.74  test_syncer_rows.py
   39.01  test_board_detail_collapsible.py
   38.36  test_board_filter_row_layout.py
   32.59  test_board_view_filter.py
   27.30  test_board_topic_view.py
   25.91  test_board_work_report.py            <-- rc=1 (failing now; see below)
   21.65  test_board_scroll_focus_jump.py
   17.04  test_board_toggle_children_gate.py
   15.71  test_board_empty_column_focus.py
   14.45  test_board_detail_nested_actions.py
   11.55  test_settings_project_groups_tab.py
   11.09  test_board_movement.py
   11.07  test_settings_shortcuts_tab.py
   10.03  test_board_detail_arrow_nav.py
    8.92  test_brainstorm_tab_switch.py
    7.16  test_monitor_shadow_zone.py
    6.49  test_brainstorm_node_action_integration.py
    5.42  test_board_picker_tab_nav.py
    5.05  test_brainstorm_proposal_preview.py
```

Cumulative share:

| files | seconds | share |
|---|---|---|
| top 1 | 164.6 | 24% |
| top 2 | 288.3 | 42% |
| top 10 | 505.9 | 74% |
| top 20 | 597.1 | 87% |
| all 174 | 687.7 | 100% |

**The remaining 154 files total ~90s combined.** Any optimization that is not
aimed at the top ~20 files is wasted effort.

### Root cause: board TUI tests boot against the LIVE task tree

The slow board modules do `os.chdir(REPO_ROOT)` in `setUpClass` and then
instantiate the real `ab.KanbanApp()` — which loads the **live** `aitasks/`
tree: 208 parent tasks + 108 child tasks. `cProfile` on a single boot:

- 5,698 `_compositor.add_widget` calls
- `stylesheet.apply` over 3,212 nodes
- ~1.1s in `compose`/`reflow`/`_arrange_root` alone

Direct A/B, same code, same machine — live tree vs. an 8-task fixture tree
(`TASK_DIR` env override):

| | `KanbanApp()` boot | `pilot.pause()` |
|---|---|---|
| live tree (316 tasks) | **2.00s** | **78ms** |
| 8-task fixture tree | **0.21s** | **25ms** |
| speedup | **9.5x** | **3.1x** |

Crucially, `TaskManager()` construction and `load_tasks()` cost only **0.08s** —
markdown/YAML parsing is *not* the bottleneck. The cost is Textual widget
mounting and CSS application, proportional to the number of task cards on
screen. There are **385 `run_test(size=...)` call sites** and **932
`pilot.pause()` calls** across the suite.

Real sleeps are a non-issue and should not be touched: only 10 literal
`time.sleep` sites totalling ~1.0s and 8 `asyncio.sleep` sites totalling 0.05s.

### Which files are on the live tree

10 of the top 20 do `chdir(REPO_ROOT)` with **zero** `TASK_DIR` / tmpdir
override (~407s combined including `test_board_bytrail_view.py`):

`test_board_bytrail_view.py`, `test_board_detail_collapsible.py`,
`test_board_filter_row_layout.py`, `test_board_view_filter.py`,
`test_board_topic_view.py`, `test_board_work_report.py`,
`test_board_scroll_focus_jump.py`, `test_board_toggle_children_gate.py`,
`test_board_empty_column_focus.py`, `test_board_detail_nested_actions.py`,
`test_board_detail_arrow_nav.py`.

(Re-enumerate at task start — this list will have drifted.)

### The fix pattern already exists in this repo

`tests/test_board_decref_doomed_attachments.py:36` defines
`_load_board_module(task_dir)`: it sets `os.environ["TASK_DIR"]`, then imports
`aitask_board.py` under a **unique synthetic module name**
(`f"aitask_board_t1093_{id(task_dir)}"`) so the cwd-relative module constants
resolve against the fixture. `tests/test_board_movement.py` uses this pattern 13
times and costs only 11s despite being a large module.

This is a migration to an established in-repo pattern, not a new invention.

### Second lever: the suite has zero parallelism

`tests/run_all_python_tests.sh:54` tries `import pytest` and silently falls back
to `python -m unittest discover` when it fails. **pytest is not installed in
`~/.aitask/venv`** (confirmed: `No module named pytest`), so the suite has
*always* run single-process and strictly serial here. t1320 already records that
the pytest branch has never executed on a real pytest install in this checkout.

A parallel-safety audit of all 174 modules found the suite unusually clean:
93/174 use `mkdtemp`/`TemporaryDirectory`, git is always done in throwaway
repos, **zero** network binds, **zero** `$HOME` writes, **zero** fixed-path
`/tmp` writes, no `setUpModule`, no golden-regeneration ordering chains.
Textual's `active_app` is a `ContextVar` (process-local), and all 3 users
set/reset it with a token.

172 of 174 files parallelize under `-n auto --dist loadfile`. `--dist loadfile`
(not the default `load`) is **mandatory** — it keeps a file's tests on one
worker, which alone fixes the fixed-tmux-socket + `kill-server` races in
`test_tmux_exec.py` and `test_launch_in_tmux_pane_pid.py`, and stops
`setUpClass` fixtures being split across workers.

Two genuine blockers:

1. `tests/test_minimonitor_concern_smoke.py:51` — fixed socket
   `ait_t1187_smoke` on the **shared** `/tmp/tmux-$UID` with no `TMUX_TMPDIR`,
   plus a fixed session name and an unconditional `kill-session`/`kill-server`.
   Two-line fix: `mkdtemp` `TMUX_TMPDIR` + `os.getpid()`-suffixed socket,
   mirroring `test_board_header_row_live.py:40`.
2. `tests/test_board_header_row_live.py` — drives the **real** `./ait board` in
   a tmux pane against the real repo, taking `.git/index.lock` via
   `git status --porcelain -- aitasks/` (`aitask_board.py:1067`), with a 45s
   boot budget that is a hard failure, not a skip. Must run in a serial
   pre/post pass.

Also note before switching backends: pytest newly collects bare module-level
`def test_*` functions that unittest ignores, and two of them take a positional
arg pytest reads as a missing fixture —
`tests/test_stats_multistage.py:132` and `:164`
(`def test_collect_inflight(tmp: Path)`). These will error at *collection*,
unrelated to parallelism. Never run the Python pool concurrently with
`tests/*.sh`, which owns the real git index.

### Projection

| change | suite wall time |
|---|---|
| today | 746s (~12.4 min) |
| fixture trees for the top ~15 board/TUI modules | ~280s |
| + pytest-xdist `-n auto --dist loadfile` | ~60-90s |

With `loadfile`, the floor is the slowest single file — so
`test_syncer_rows.py` (124s, 136 tests, no live-tree coupling; its cost is app
boots + 130 `pilot.pause()` calls) becomes the binding constraint once the board
files are fixed, and may need splitting or its own analysis.

## Correctness bonus: this fixes two open bugs

The live-tree coupling is not only slow, it is a **live correctness defect**.
`tests/test_board_work_report.py` returned **rc=1 in the timing sweep — it is
failing right now**. Both t1346 and t1352 are folded into this task; their full
content is preserved below.

## Suggested approach

Order matters — do the fixture migration first, since it is the larger,
lower-risk win and it also fixes the folded bugs.

1. **Re-measure first.** Re-run the per-file timing sweep to get a current
   baseline (the numbers above are from 2026-07-31 and the tree grows). Record
   the baseline in the plan; the acceptance criterion should be a measured
   before/after on the same machine, one denominator, not a projection.
2. **Build a shared board-fixture helper** under `tests/lib/` that creates a
   small task tree (a handful of parents + children spanning the board columns
   and the metadata the tests actually assert on) and loads `aitask_board` via
   the existing `_load_board_module(task_dir)` pattern. Do **not** fork that
   logic — extract/reuse it so there is one seam.
3. **Migrate the live-tree board modules** to the helper, one at a time,
   verifying each still asserts the same property. Several tests currently
   `skipTest` when the live tree lacks a populated column — those skips should
   become unconditional real assertions against the fixture.
4. **Fix the two folded bugs as part of step 3** — `test_hidden_cards_still_listed`
   stops depending on live data entirely.
5. **Decide separately** on t1352's second question (below): whether an
   unparseable task filename should produce a visible warning in the board /
   `ait ls` rather than being silently dropped by `TaskCard._parse_filename`.
   This is a product decision, not a test fix; if it is kept, it likely deserves
   its own follow-up task rather than being buried in a perf change.
6. **Then the parallel lane**: add pytest + pytest-xdist to the framework venv
   (check how `aitask_setup.sh` provisions venv deps — new deps need to be
   declared where the other TUI deps are), fix
   `test_minimonitor_concern_smoke.py`'s socket isolation, carve
   `test_board_header_row_live.py` into a serial pass, fix the two
   `test_stats_multistage.py` collection errors, and pin `--dist loadfile` in
   `run_all_python_tests.sh`.
7. **Preserve the t1179 result contract.** `run_all_python_tests.sh` must keep
   emitting `PYTHON SUITE: PASSED|FAILED (runner=..., exit=N)` as the last line
   on stderr, derived from the backend's real exit status, through both
   backends. Adding xdist must not weaken that.
8. **Add a guard against regression.** The live-tree coupling will creep back.
   Consider a test asserting that no `tests/test_board_*.py` module does
   `chdir(REPO_ROOT)` without a `TASK_DIR` override — and prove the guard can
   actually fail (negative control) before trusting it.

## Risks / open questions

- **pytest changes collection semantics.** Switching the default backend means
  the suite runs a different set of tests than it does today. The first pytest
  run will surface pre-existing latent failures (masked `sys.path` bootstraps —
  see `tests/lib/import_isolated.py:8-16` — and the module-level `def test_*`
  functions). Budget for that; do not conflate them with parallelism bugs.
- **Making pytest mandatory** would change the framework's dependency surface
  for every user, not just this machine. Prefer keeping the unittest fallback
  working and treating the xdist lane as opt-in / opt-out-able, unless the user
  decides otherwise.
- **xdist under load** makes `test_board_header_row_live.py`'s 45s boot budget
  and `test_board_movement.py`'s latency benchmark the most plausible flakes.
  Never set `AITASK_BOARD_BENCH=1` under `-n auto`.
- **Fixture trees can weaken coverage.** Some board tests genuinely exercise
  scale (many cards, many columns). Where a test's property depends on volume,
  the fixture must reproduce that shape rather than shrinking it away — check
  each migrated assertion rather than assuming.

## Merged from t1346: board work report test reads live tree


## Origin

Spawned from t1216_3 during Step 8b review. It made that task's full-suite run
red for a reason unrelated to any code change in it.

## Upstream defect

- `tests/test_board_work_report.py:483 — WorkReportFullColumnUnderSearchTests::test_hidden_cards_still_listed asserts sl.option_count == len(col_tasks) against the LIVE aitasks/ tree, so any concurrent task-file change during the ~12-minute suite makes it fail (observed 145 != 146).`

## Diagnostic context

The test snapshots the live board column with
`app.manager.get_column_tasks(col_id)`, then applies a search filter, opens the
work-report screens, and asserts the resulting `SelectionList.option_count`
equals the length of that earlier snapshot. It even calls `skipTest` when the
live tree has no populated column, so the dependence on real data is
acknowledged in the test itself.

Observed during t1216_3: `AssertionError: 145 != 146` in a 2788-test run lasting
746s. During that window the t1216_3 workflow itself committed task-status and
gate-ledger changes to `aitasks/`, and other sessions may have too. Any task
appearing or moving column mid-run shifts the count.

Established as independent of t1216_3 rather than assumed: importing
`aitask_board` loads none of the modules that task changed
(`monitor.monitor_app`, `monitor.monitor_shared`, `monitor.minimonitor_app`) —
verified by inspecting `sys.modules` after the import.

## Impact

Every task that runs `bash tests/run_all_python_tests.sh` can hit a red suite
for no reason connected to its own change. That trains agents and humans to
discount the suite verdict, which is the real cost — the framework's own
convention is to read the last line as authoritative.

## Suggested fix

Decouple the assertion from live data: build the board over a fixture task tree
(as the other board tests do), or re-read the column immediately before the
comparison so both sides come from the same moment. Do not simply widen the
assertion to a range — that would keep the nondeterminism and hide real
regressions.

## Merged from t1352: fix work report test live tree coupling


## Origin

Spawned from t1216_4 during Step 8b review.

## Upstream defect

- `tests/test_board_work_report.py:483` — `test_hidden_cards_still_listed`
  asserts `sl.option_count == len(col_tasks)` against the **live** task tree,
  but `action_work_report` (`aitask_board.py:7271`) deliberately skips any task
  whose filename `TaskCard._parse_filename` cannot parse (`if not task_num:
  continue`). A single malformed task file anywhere in the first populated
  work-report column therefore fails the whole Python suite. Currently
  triggered by `aitasks/t_refresh_codeagent_suite_default_model_expectations.md`
  (created 2026-07-29), whose filename carries no task number.

## Diagnostic context

Surfaced while verifying t1216_4 (shadow spawn ported to `ait monitor`). The
full suite reported `2951 tests, 1 failure` with
`AssertionError: 150 != 151`. t1216_4 touches only the monitor/shadow modules
and `agent_launch_utils`; it does not touch `aitask_board.py`, so the failure
could not originate there.

Reproduced independently of the test, from live data alone:

```
column tasks: 151
kept: 150  dropped(unparseable): 1
   DROPPED: t_refresh_codeagent_suite_default_model_expectations.md
duplicate ids: []
```

i.e. `manager.get_column_tasks("unordered")` returns 151 rows while the
`SelectionList` built by `action_work_report` legitimately carries 150. The
production skip is correct — a task with no id cannot be passed to the work
report as `--tasks <id>` — so the defect is in the test's equality assumption,
not in the board.

Two things are worth deciding separately:

1. **The test** couples a strict equality to whatever happens to be on disk.
   Any malformed task file, now or later, breaks an unrelated suite run and
   costs a diagnosis cycle.
2. **The data artifact** — a task file whose filename has no task number. Worth
   checking which creation path produced it, and whether the board/`ait ls`
   surfaces should warn about unparseable task filenames rather than silently
   dropping them.

## Suggested fix

Make the assertion mirror the production filter: compare `sl.option_count`
against the number of column tasks whose filename actually parses (or assert
`<=` plus an explicit parse-failure count), so the test measures the
"search-hidden cards are still listed" property it is named for rather than the
tidiness of the live task tree. Separately, decide whether the numberless task
file should be renamed/repaired and whether unparseable filenames deserve a
visible warning.

## Folded Tasks

The following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.

- **t1346** (`t1346_board_work_report_test_reads_live_tree.md`)
- **t1352** (`t1352_fix_work_report_test_live_tree_coupling.md`)
