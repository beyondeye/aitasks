---
Task: t1243_1_movement_baseline_and_harness.md
Parent Task: aitasks/t1243_board_task_groups_and_fast_reordering.md
Sibling Tasks: aitasks/t1243/t1243_10_group_collapse_and_filtering.md, aitasks/t1243/t1243_11_group_formation_and_block_moves.md, aitasks/t1243/t1243_12_group_membership_commands.md, aitasks/t1243/t1243_13_documentation.md, aitasks/t1243/t1243_14_retrospective_benchmark.md, aitasks/t1243/t1243_15_manual_verification_board_groups_and_reordering.md, aitasks/t1243/t1243_2_board_field_persistence_seam.md, aitasks/t1243/t1243_3_gap_indexing.md, aitasks/t1243/t1243_4_render_filter_scoping.md, aitasks/t1243/t1243_5_lateral_dom_transplant.md, aitasks/t1243/t1243_6_multiselect_marking.md, aitasks/t1243/t1243_7_move_to_column_command.md, aitasks/t1243/t1243_8_boardgroup_field_and_model.md, aitasks/t1243/t1243_9_group_focus_and_rendering.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-28 15:06
---

# t1243_1 — Movement baseline and harness

## Context

`ait board` reordering is slow and writes more task files than the user asked
to move. t1243 decomposes the fix into 14 children; **this is child 1**.

There are **zero board-movement tests today**. Children 3, 4, 5 and 11 all
change how the board writes `boardidx` / `boardcol` or how it re-renders after
a move, so the characterization harness and the performance baseline must exist
**before** any of them. This child also owns the **pre-registered** measurement
method and the success rules that decide whether t1243_4 and t1243_5 are built
as planned — "the render pass is the wall" is currently an inference by
elimination, not a measurement.

Deliverable: `tests/test_board_movement.py` (new, the entire deliverable), plus
a baseline table and a checkpoint decision recorded in
`aiplans/p1243_board_task_groups_and_fast_reordering.md`.

## Anchor re-verification — done, all anchors hold

Re-checked at current `HEAD`, so the implementation step need not repeat it:

- `aitask_board.py` is **still 9043 lines** — no drift since t1243 was planned.
- `TASKS_DIR = task_dir()` at **line 66**, module-load constant; `METADATA_FILE`,
  `USERCONFIG_FILE`, `TASK_TYPES_FILE`, `GATES_REGISTRY_FILE` all derive from it
  at import time.
- `TaskManager.normalize_indices` writes **only** when `task.board_idx != (i+1)*10`.
- `move_task_col` appends at `max_idx + 10`; `swap_tasks` exchanges two indices;
  `Task.save()` does **not** bump `updated_at` (only `save_with_timestamp` does).
- `run_all_python_tests.sh` runs `pytest tests/test_*.py` in **one** process;
  **16** test files import `aitask_board`. `test_board_movement.py` sorts after
  `test_board_inflight_view.py`.
- Textual **8.2.7**, CPython 3.14.6, interpreter `/home/ddt/.aitask/venv/bin/python`
  (`require_ait_python`). `ShiftRight`/`ShiftLeft`/`ShiftUp`/`ShiftDown` are real
  Textual keys.

### Textual timing primitives — read from the installed 8.2.7

Load-bearing for §7, so recorded here:

- **`Pilot.pause()` is unusable inside a timed region.** With `delay=None` it
  calls `wait_for_idle(0)`, whose loop **always** runs at least one
  `await sleep(SLEEP_GRANULARITY)` with `SLEEP_GRANULARITY = 1/50` **before** any
  idle test — a hard floor of **≈ 20 ms of synthetic sleep per call**. Two calls
  per sample would inject ~40 ms into a keypress plausibly costing single-digit
  ms, diluting every attribution ratio and capable of falsely refuting the 40 %
  premise on its own.
- **`Pilot.press` is clean.** It awaits `_wait_for_screen()`, which posts a
  `call_later` decrement to the app and every widget and waits on an
  `asyncio.Event` — event-driven, **no sleep**.
- **`call_after_refresh` posts an `InvokeLater` *message***, not a frame-timer
  callback, so the deferral is message-pump latency and is drained by
  `_wait_for_screen`. FIFO per pump means an `InvokeLater` posted by the key
  handler is processed before the decrement `_wait_for_screen` enqueues
  afterwards.

Consequently §7 closes its timed region on **explicit completion events** and
**never calls `pilot.pause()` inside it**.

### The two move paths are structurally different — this drives everything below

| | lateral (`shift+←/→`) | vertical (`shift+↑/↓`) | extreme (`ctrl+↑/↓`) |
|---|---|---|---|
| writes | `move_task_col` + `normalize_indices` on **both** columns | `swap_tasks` + `normalize_indices` (1 column) | direct `±10` write + `normalize_indices` |
| render | `refresh_columns({src,dst})` → `_recompose_column` **×2** | `_swap_adjacent_cards` → DOM `move_child`, **no recompose** | `refresh_column` → `_recompose_column` ×1 |
| `apply_filter` | **deferred** (`call_after_refresh`) | **synchronous**, inside `_swap_adjacent_cards` | **deferred** |
| `refresh_git_status` | yes | yes | yes |

Vertical has **no recompose pass at all** on the fast path. Any pooled
"apply_filter + recompose share" statistic is therefore not a meaningful
quantity, which is what §7 fixes.

## What the verify pass changed

Findings that are load-bearing and were **not** in the previous plan. Each has
a step below.

1. **`_is_phantom_stub` silently drops fixture files.** `load_tasks` skips any
   task whose frontmatter keys are a subset of `BOARD_KEYS` (`boardcol`,
   `boardidx`). A fixture carrying *only* board fields loads **zero** tasks and
   every scenario passes vacuously.
2. **`TASK_DIR` alone does not isolate the board; cwd is a second seam.**
   `_task_git_cmd()` resolves `DATA_WORKTREE = Path(".aitask-data")` **relative
   to cwd**, and `refresh_lock_map()` shells `./.aitask-scripts/aitask_lock.sh`
   relative to cwd. `os.chdir(REPO_ROOT)` — what every existing board test does
   — points `refresh_git_status` at the **real** repo.
3. **The fixture must reproduce production's branch-mode git topology.** This
   checkout has `aitasks` → `.aitask-data/aitasks` with `.aitask-data/.git`
   present, so production runs `git -C .aitask-data status --porcelain -- aitasks/`,
   not root-repo git. **And `TASK_DIR` must stay relative**: `is_modified`
   compares `str(task.filepath)` against porcelain paths like
   `aitasks/tN.md`, so an absolute `TASK_DIR` never matches and **no card ever
   renders the modified marker** — understating render cost as well as git cost.
4. **Fixture files must be written through `serialize_frontmatter`.**
   `Task.save()` re-serializes with board keys forced last; hand-written YAML
   would change bytes on the *first* write from normalization alone.
5. **Spy and differ disagree by design.** `Task.save()` is byte-identical when
   values are unchanged, so a counted write need not be a changed file. The flip
   table records both numbers independently rather than deriving one from the other.
6. **Write counts and hashes do not prove correctness.** A regression that writes
   the expected files with the wrong `boardcol`/`boardidx`, or that clobbers
   `status` / the body, passes a count+hash oracle. §4 adds final-state,
   ordering, identity and non-board-survival assertions.
7. **The differ must not snapshot the whole temp tree.** `git status` refreshes
   `.git/index`, and IPC JSON inside the root would pollute the changed-path set.
8. **Lateral ping-pong is only stationary for a bottom-of-column card**, because
   `move_task_col` appends at `max_idx + 10`. Warm-up must also be a whole
   number of pairs.
9. **The timed region must close on an explicit completion event**, never on
   `pilot.pause()` (≥ 20 ms of synthetic sleep per call — see above), and must
   report the deferral gap separately so message-pump wait is not silently
   attributed to rendering.
9b. **`other_i ≥ 0` is a consistency check, not a non-overlap proof** —
   uninstrumented time can absorb a double-counted span and still leave a
   positive residual. Non-overlap needs an active-span stack.
9c. **The negative control mutates `os.environ` in the shared pytest process**
   and must restore it, or later tests and subprocesses inherit a `TASK_DIR`
   pointing at a deleted temp tree.
10. **The full benchmark cannot run on every suite invocation** (200 cards ×
    ~90 samples). Env-gated, with an ungated smoke so the path cannot rot.

## Key files

- `tests/test_board_movement.py` — **new**, the entire deliverable.
- `aiplans/p1243_board_task_groups_and_fast_reordering.md` — the disambiguated
  decision formula (§0), then the baseline table and checkpoint decision (§8).

Reference patterns (read, do not modify):

- `tests/test_task_dir_module_constants.py::_probe` — the subprocess-probe
  pattern (`sys.executable`, `PYTHONPATH` over `.aitask-scripts/{board,lib}`,
  `TASK_DIR` in `env`). Closest prior art.
- `tests/test_board_empty_column_focus.py` — live-repo Pilot harness
  (`asyncio.run` wrapper, `run_test(size=…)`, `_settle` pause loop).
- `.aitask-scripts/lib/task_yaml.py` — `serialize_frontmatter`, `BOARD_KEYS`,
  `normalize_board_idx`.

## Implementation

### 0. Record the disambiguated decision formula in the parent plan FIRST

**This step precedes any measurement**, otherwise "pre-registered" is not true.

The parent plan's rule — "`apply_filter` + column recompose account for ≥ 40 %
of median keypress latency" — is **not computable as written**: it mixes
per-span totals with a per-sample median, `refresh_columns` contains
`_recompose_column` so the pair can be double-counted, it does not say whether
the axes are judged separately despite vertical having no recompose, and it does
not say whether the denominator includes message-pump deferral time.

Append §7's formula table and per-axis decision rules to
`aiplans/p1243_board_task_groups_and_fast_reordering.md` under
"Measurement precedes redesign", labelled as a **disambiguation of the
pre-registered rule**, and commit it with `./ait git` **before** running the
benchmark. Three things are pinned; **no threshold changes — 40 % / 30 % stand**:

1. Ratios are computed **per sample, then medianed** — never as a ratio of
   aggregates.
2. The axes are **judged separately**; each of t1243_4 / t1243_5 is decided by
   the ratio for the span it actually removes.
3. **One denominator for every rule: wall-clock `e2e_i`.** Both the 40 %
   attribution gate and the 30 % target divide by the same per-sample
   wall-clock keypress latency — exactly the parent plan's "share of median
   keypress latency". `defer_i` is reported as **diagnostic data only** and is
   never subtracted from a denominator.

   *Why not an "active work" denominator:* subtracting deferral makes the two
   rules incoherent. At `e2e` = 20 ms, `defer` = 10 ms, render = 5 ms, an
   active-work denominator reports a **50 %** render share — clearing the 40 %
   gate — while removing rendering entirely improves user-perceived latency by
   only 5/20 = **25 %**, which cannot meet the 30 % target. A gate must not
   greenlight work that provably fails its own target. Pilot's synthetic idle is
   already excluded by construction (no `pause()` in the timed region), so what
   remains in `e2e_i` is real production latency and belongs there.

4. **Child opportunity is judged on each child's *combined removable* cost, not
   on any single span** — see §7. No individual-component 40 % test is used to
   refute a child.

And one behavioural amendment, recorded in the same commit: **a missed gate
triggers the Performance-Gate Confirmation Checkpoint (§8), not an automatic
revise/replace/postpone.** The parent plan's "Decision checkpoint" paragraph and
this task file's Verification bullet both currently read as an automatic action;
both are updated so the AC matches the behaviour, rather than the behaviour
silently diverging from the AC.

### 1. Temp-tree fixture — production topology

```
<tmp>/tree/                     # cwd of the child process
  .aitask-data/
    .git/                       # git init here → _task_git_cmd() = git -C .aitask-data
    aitasks/
      metadata/board_config.json         # columns + column_order (project layer)
      metadata/board_config.local.json   # settings (user layer)
      t<i>_fixture.md × N
  aitasks -> .aitask-data/aitasks         # symlink, as in production
<tmp>/ipc/                      # params.json / result.json live OUTSIDE the tree (finding 7)
```

- `TASK_DIR="aitasks"` — **relative**, so `str(task.filepath)` matches porcelain
  paths and `is_modified` behaves as in production (finding 3).
- `git init` inside `.aitask-data`, then one commit of `aitasks/`, using
  `-c user.email=… -c user.name=…` plus `GIT_AUTHOR_*` / `GIT_COMMITTER_*` env so
  it is independent of global config. A plain repo (not a linked worktree of the
  real repo) is used deliberately: `_task_git_cmd` only tests
  `(DATA_WORKTREE/".git").exists()`, git resolves a `.git` dir and a gitfile to a
  repo before doing any work, and creating worktrees of the real repo under
  `/tmp` risks writing into it. The residual difference is recorded in the
  baseline table.
- `settings`: `auto_refresh_minutes: 0` (the timer must not perturb samples),
  `collapsed_columns: []` (lateral ping-pong must not skip a column).
- Task files are `serialize_frontmatter({"status": …, "priority": …, "issue_type": …,
  "boardcol": …, "boardidx": …}, body, key_order)` — the non-board keys are what
  keep `_is_phantom_stub` from dropping them (finding 1), and they are also the
  payload the non-board-survival assertion checks.
- No card is placed in `unordered`, so `cols == column_order` in
  `_move_task_lateral`; the child asserts `get_column_tasks("unordered") == []`.
- Starting `boardidx` values are **explicit per scenario** — canonical
  (`10,20,30,…`) and deliberately non-canonical rows are separate flip-table
  entries, because `normalize_indices` writes only on mismatch.
- A `legacy` fixture variant (no `.aitask-data`, no symlink) exists for the
  topology-comparison test in §7.

### 2. Subprocess runner

The scenario body runs in a **child interpreter** — `TASKS_DIR` is bound at
import and 16 board tests have already imported `aitask_board` by the time this
file runs in the full suite.

- Same file, dispatched by `--child <params.json> <result.json>` from the
  `__main__` block (which otherwise calls `unittest.main()`).
- `subprocess.run([sys.executable, __file__, "--child", pin, pout], cwd=tree_root,
  env={…, "TASK_DIR": "aitasks", "PYTHONPATH": board:lib,
  "PYTHONDONTWRITEBYTECODE": "1"})`.
- **cwd is the tree root**, never `REPO_ROOT` (finding 2).
- Results go to the **JSON path in argv**, which lives in `<tmp>/ipc/`. Never
  stdout — Textual and pytest write there. Non-zero exit → fail with the child's
  captured stderr.

### 3. Oracles: spy, differ, and instrumentation

Installed in the child before the app is constructed.

- **Call-count spy** wrapping `Task.reload_and_save_board_fields`, per filename.
- **Path + content-hash differ** over an **explicit allowlist** (finding 7):
  `aitasks/**/*.md` plus `aitasks/metadata/board_config*.json`, resolved through
  the symlink. `.git/` and `<tmp>/ipc/` are outside it by construction.
- **Span instrumentation** — four leaves claimed to be **mutually
  non-overlapping**, each a `perf_counter` wrapper accumulating per-sample totals
  and a call counter: `apply_filter`, `_recompose_column`, `refresh_git_status`,
  `reload_and_save_board_fields`. `refresh_column` / `refresh_columns` are wrapped
  **inclusively for reporting only** and excluded from every formula, since they
  contain `_recompose_column`.

  **The non-overlap claim is proved, not assumed (finding 9b).** The wrappers
  share a per-thread **active-span stack**: on entry, if the stack for this
  thread is non-empty the wrapper records a `(outer, inner)` **nesting
  violation**; it pushes on entry and pops on exit (in a `finally`). Any recorded
  violation **fails the run**. Keying by thread id keeps a `@work` thread from
  producing a false positive. The `other_i ≥ 0` residual (§7) is retained as a
  *consistency* check only — it cannot prove non-overlap, because uninstrumented
  time can absorb a double count and still leave a positive residual.

- **Deferral instrumentation — one non-overlapping interval per sample.** Summing
  callback ages (`Σ(started_at − queued_at)`) is wrong: `refresh_columns` queues
  `apply_filter` and `_refocus_card` at essentially the same instant, so the
  refocus callback's age contains **both** the same scheduler wait *and*
  `apply_filter`'s execution time — the sum double-counts elapsed time and could
  drive the residual negative.

  Instead measure a **single interval**: `sync_end` is stamped when the
  synchronous action body returns (wrapper on `_move_task_lateral` /
  `_move_task_vertical` / `_move_task_to_extreme`), `first_deferred_start` is
  stamped at the entry of the first deferred callback to run, and
  `defer_i = max(0, first_deferred_start − sync_end)`. Non-overlapping with every
  instrumented leaf by construction (it is pure wait between them).

  `defer_i` is **diagnostic only** (§0 pin 3) — it never enters a denominator.
  The consistency check is `defer_i ≤ other_i`, i.e. it is contained in the
  unattributed residual rather than added to it.

### 4. Correctness oracle — final board state, not just write counts

After each scenario the child re-reads every fixture file **from disk** and
reports:

- `final_state`: `{filename: {"boardcol", "boardidx"}}`.
- `board_order`: `{col_id: [filenames]}` as returned by the board's own
  `get_column_tasks`.
- `loaded`: sorted parent filenames actually loaded, and the count.
- `nonboard_diff`: for every fixture file, the metadata (minus `BOARD_KEYS`) and
  the body compared against the fixture's expected values — a list of the files
  where anything other than a board key changed.
- `moved`: the filename the scenario moved.

The parent then asserts, per scenario:

- exact spy `writes` and exact `changed`/`added`/`removed` path sets;
- exact `final_state` for the moved task **and** for every task in the affected
  columns — so "right file written with the wrong value" fails;
- `nonboard_diff == []` — `status` / `priority` / `issue_type` / body survive even
  in files that legitimately changed;
- `loaded == expected_filenames` and `len(loaded) == N` — a silently emptied or
  partially-loaded fixture fails instead of passing vacuously;
- **ordering via independent ground truth:** the test recomputes the expected
  order from `final_state` using the documented key
  `(normalize_board_idx(idx), filename)` and asserts it equals `board_order` —
  two independent paths to the same answer rather than the board grading itself.

### 5. Characterization flip table

A module-level dict, scenario → the full expected record from §4, asserted
**exactly** (`assertEqual`, never `assertGreater`):

| scenario | op | starting state |
|---|---|---|
| `lateral_canonical` | `_move_task_lateral(+1)` | both columns canonical |
| `lateral_gapped` | `_move_task_lateral(+1)` | source column non-canonical |
| `vertical_swap` | `_move_task_vertical(+1)` | canonical |
| `extreme_top` | `_move_task_to_extreme(-1)` | canonical |
| `extreme_bottom` | `_move_task_to_extreme(+1)` | canonical |
| `shift_column` | `_shift_column(+1)` | canonical — expect **0** task writes |

Expected values are recorded from the first run, then frozen. t1243_3 must
consciously edit this table; an inline comment states that a silent pass after
its rewrite is a bug in the table.

### 6. Proving the harness can fail, and the isolation negative control

**Mutation test (automated, no manual revert).** The child accepts
`"mutate": "skip_normalize"`, which no-ops `TaskManager.normalize_indices` after
import. A dedicated test runs `lateral_canonical` under it and asserts the frozen
record does **not** match — the oracle is shown to discriminate inside the suite.

**Isolation negative control (read-only, deterministic in both run modes).**
Import `aitask_board` in the parent (reproducing the cached-module state the full
suite creates), then — inside
`unittest.mock.patch.dict(os.environ, {"TASK_DIR": str(tmp_tree)})`, which
restores the prior value (or its absence) even on failure — assert:

1. `aitask_board.TASKS_DIR == Path("aitasks")` — the override was a no-op;
2. `Path(os.environ["TASK_DIR"]).resolve() != (REPO_ROOT / aitask_board.TASKS_DIR).resolve()`
   — the cached root and the intended root are demonstrably different roots;
3. with cwd at `REPO_ROOT`, a read-only `glob(str(aitask_board.TASKS_DIR / "*.md"))`
   returns a **non-empty** set that contains real repo task filenames and **none**
   of the `t*_fixture.md` names.

(3) is what upgrades the control from "proves caching" to "proves the in-process
variant reads the real tree", and it touches no repository data: no
`TaskManager` is constructed and nothing is written.

**Env hygiene (finding 9c).** The full suite runs in **one** interpreter, so a
leaked `TASK_DIR` would point later tests — and any subprocess they spawn — at a
deleted temp tree. `patch.dict` is the mechanism; the test additionally asserts
after the block that `os.environ.get("TASK_DIR")` equals its pre-test value. No
other test in this file sets `TASK_DIR` in the parent process at all — the child
runner passes it through `env=` only.

### 7. Pre-registered benchmark — unambiguous formula

**Method.** 200 parent cards over 5 columns, warm headless Pilot
(`run_test(size=(200, 60))`), production branch-mode topology.

**Stationarity (finding 8).** The moved card starts at the **bottom** of its
column — the only position for which `move_task_col`'s append-at-`max_idx + 10`
makes right→left restore the exact pre-state. Ping-pong pairs:

- lateral: `shift+right` then `shift+left` between two adjacent non-collapsed
  columns;
- vertical: `shift+down` then `shift+up` with the card mid-column.

Warm-up is **3 complete pairs (6 samples), discarded**; then **20 complete pairs
(40 samples)** recorded per axis. After **every** pair the child asserts the full
relevant pre-state is restored — `final_state` and `board_order` for both
affected columns equal the pair's starting snapshot. A mismatch **fails the run**
rather than drifting.

**Timed region (finding 9) — event-closed, no `pilot.pause()`, uniform across axes:**

```
filter_done.clear(); refocus_done.clear()        # asyncio.Events set by the wrappers
t0 = perf_counter()
await pilot.press(key)                            # _wait_for_screen(): event-driven, no sleep
await asyncio.wait_for(refocus_done.wait(), timeout=5)
t1 = perf_counter()
```

`_refocus_card` / `_refocus_column` is the **last** deferred callback every move
path queues (`refresh_columns` and `refresh_column` queue `apply_filter` first,
then `_queue_refocus`; `_swap_adjacent_cards` runs `apply_filter` synchronously
and then the path queues the refocus), so its completion is the true
"keypress fully applied" point and is uniform across all three ops.

**`pilot.pause()` must not appear anywhere inside the timed region** — it costs
≥ 20 ms of `asyncio.sleep` per call. It is still used freely *outside* the
region, for fixture settling. Each sample records `press_covered` — whether both
events were already set when `press` returned, i.e. whether `_wait_for_screen`
had already drained the `InvokeLater`. If it is uniformly true, the report states
that the explicit wait contributed nothing; if not, `defer_i` quantifies what it
contributed.

**Per-sample validity — all four required, else the run fails (never averaged in):**

1. write-spy delta > 0 (a zero-write sample is a rejected action);
2. the `apply_filter` counter incremented inside the timed region;
3. **zero nesting violations** on the active-span stack (§3) — this, not the
   residual, is the non-overlap proof;
4. `other_i = e2e_i − (af_i + rc_i + git_i + save_i) ≥ 0`, plus
   `defer_i ≤ other_i` and `rc_i ≤ refresh_cols_inclusive_i` — consistency
   checks; a violation still fails the run, but the plan does **not** claim the
   residual proves non-overlap (that is invariant 3's job). `defer_i` sits
   *inside* `other_i`; it is never added to the leaf sum.

**Aggregation (per sample, then per axis).** For each valid sample `i` of axis
`A`, using the four exclusive leaves:

| quantity | formula |
|---|---|
| `E2E_A` | `median_i(e2e_i)`, and `p90_i(e2e_i)` — wall clock, the sole denominator |
| `DEFER_A` | `median_i(defer_i)`, `median_i(defer_i / e2e_i)` — **diagnostic only** |
| `R_pair_A` | `median_i((af_i + rc_i) / e2e_i)` — the workstream premise quantity |
| `R_af_A` | `median_i(af_i / e2e_i)` |
| `R_rc_A` | `median_i(rc_i / e2e_i)` |
| `R_git_A` | `median_i(git_i / e2e_i)` |
| `R_rm4_A` | `median_i((af_i + git_i) / e2e_i)` — t1243_4's combined removable cost |
| `R_rm5_A` | `median_i(rc_i / e2e_i)` — t1243_5's removable cost (lateral only) |

Ratios are computed **per sample and then medianed** — never as a ratio of
aggregates, and never by dividing 40-sample span totals by a per-sample median.
Axes are **never pooled**; `A ∈ {lateral, vertical}`.

**Decision rules — 40 % for the combined workstream, per-child gates on combined
removable cost.** Applying 40 % independently to `rc`, `af` or `git` is a
false-negative gate: at `rc` = 15 %, `af` = 15 %, `git` = 12 % no component
reaches 40 %, yet t1243_4 removes 27 % and t1243_5 removes 15 % — jointly well
past the 30 % target. So:

- **Workstream-B premise (the parent plan's rule, verbatim, unchanged)** =
  `R_pair_lateral ≥ 0.40`. Lateral is the path the premise is about — it is the
  one that recomposes two columns. `R_pair_vertical` is reported alongside; if
  lateral holds and vertical does not, the premise is recorded as holding **for
  the lateral path only**. **This is the only place the 40 % threshold is used.**
- **t1243_4 opportunity gate:** `max(R_rm4_lateral, R_rm4_vertical) ≥ 0.30` —
  its levers are scoped `apply_filter` **and** killing the per-keypress
  `git status`, so its removable cost is `af + git` taken together.
- **t1243_5 opportunity gate:** `R_rm5_lateral ≥ 0.30` — it removes only the
  recompose, and only laterally, so its target is evaluated on lateral too.
- Each child's gate threshold **is** its own target (30 %), because a child whose
  total removable cost is below its target cannot reach it even with perfect
  removal. This is a **necessary, not sufficient** condition: clearing it does
  not promise the target, only that the target is not arithmetically impossible.
  A miss is evidence for §8, never an automatic action.
- **Target rule** — ≥ 30 % reduction in **median keypress latency, per axis**,
  against wall-clock `E2E_lateral` / `E2E_vertical`; t1243_5 is judged on lateral
  only. Pooled comparison was never well-defined; t1243_14 re-runs the identical
  method per axis.

**Topology comparison.** The same lateral measurement is also run against the
`legacy` fixture, and both `R_git_lateral` values are reported. The checkpoint
uses the **branch-mode (production)** number; the legacy number documents how
much the topology matters (concern 2).

**Gating (finding 10).** The full run is behind `AITASK_BOARD_BENCH=1`; an
ungated smoke (20 cards, 2 pairs, same code path, no thresholds, validity checks
still active) runs in every suite invocation so the benchmark cannot rot.

### 8. Decision checkpoint — the last step

Run the gated benchmark and evaluate §7's rules.

**If every rule holds** → append the baseline table to
`aiplans/p1243_board_task_groups_and_fast_reordering.md`: per-axis median and
p90 wall-clock `e2e`, median `defer` (absolute and as a share, labelled
**diagnostic**), all six ratios per axis, per-span totals, the residual `other`
share, `press_covered`, sample/warm-up counts, every method parameter, and both
git topologies. Commit with `./ait git`. Done.

**If any rule is missed → the Performance-Gate Confirmation Checkpoint below
runs. The agent takes no corrective action on its own.**

#### Performance-Gate Confirmation Checkpoint

**⚠️ NON-SKIPPABLE — the `fast` profile, `post_plan_action`, auto mode, and any
"work without stopping" directive do NOT bypass this checkpoint.** It is a
decision gate, not a routine confirmation: a missed number is evidence, and what
it *means* for the roadmap is the user's call, not the agent's. This is a
deliberate amendment to the task file's and parent plan's current wording
("revise, replace, or postpone t1243_4 and t1243_5"), which reads as an
automatic action; §0 records the amendment in the parent plan and the task file's
Verification bullet is updated to match, so the AC and the behaviour agree.

Applies to **both** gates:

- the **pre-implementation gates** measured here — the 40 % workstream premise
  (`R_pair_lateral`) and the per-child 30 % opportunity gates (`R_rm4`,
  `R_rm5`) — and
- the **post-implementation 30 % target rule**, whenever t1243_4, t1243_5 or
  t1243_14 evaluates it against this baseline. The contract is defined here
  because this child owns the rules; those children invoke this same checkpoint.

**On a miss, the agent MUST NOT:**

- revise, replace, rewrite, or postpone `t1243_4` / `t1243_5` (or any other task);
- revert, discard, stash, or reset any code — **the working tree is preserved
  exactly as it is** until the user decides;
- proceed as though the gate passed, or quietly re-scope to make it pass.

**The agent MUST**, in this order:

1. **Present the evidence** — which rule was missed, its measured value against
   its threshold, and the per-axis ratio table, so the dominant span is visible
   rather than asserted.
2. **State the reasoning** — what the numbers imply about where the time actually
   goes, and what each option below would cost or buy. A recommendation is fine;
   a decision is not.
3. **Ask via `AskUserQuestion`** — "Performance gate missed: \<rule\> measured
   \<value\> against \<threshold\>. How would you like to proceed?" with exactly
   these options:
   1. **Continue with the original work despite the result** — keep the child's
      scope as planned; record the miss and proceed.
   2. **Revise the child's scope based on the measured bottleneck** — re-target
      it at the span the data says dominates.
   3. **Postpone the child** — leave it unimplemented and unblocked for a later
      decision.
   4. **Keep the already-written implementation despite missing its target** —
      applies to the post-implementation 30 % case; the code stands as-is.

   (Option 4 is offered only when an implementation already exists; options 1–3
   are always offered.)
4. **Act only on the chosen option**, then **record in the parent plan**: the
   full measurement data, which rule was missed, the options presented, the
   user's choice, and any scope change that followed. Commit with `./ait git`.

Nothing is written to `t1243_4` / `t1243_5` before step 4.

## Verification

- `python3 -m pytest tests/test_board_movement.py -v` — all pass.
- `bash tests/run_all_python_tests.sh` — all pass, **and** every scenario reports
  the same frozen record as the standalone run (each child result carries its
  resolved `TASKS_DIR`, asserted to be inside the temp tree in both modes).
- The mutation test (§6) proves the flip table exits 1 on a reverted behaviour.
- The negative control (§6) proves the in-process `TASK_DIR` variant enumerates
  the real `aitasks/` tree.
- Every scenario asserts `loaded == expected` and `nonboard_diff == []`.
- Every benchmark pair asserts full pre-state restoration; the active-span stack
  reports **zero nesting violations**, which is what proves the spans do not
  overlap.
- A grep-level guard in the test asserts `pilot.pause(` appears nowhere between
  the `t0`/`t1` stamps (the timed region is a single small helper, so this is a
  review-time invariant plus the `press_covered` datum that quantifies it).
- The negative control restores `os.environ["TASK_DIR"]`, asserted explicitly
  after the `patch.dict` block.
- `git -C .aitask-data status --porcelain -- aitasks/` is unchanged by a full test
  run — no file under the repo's real `aitasks/` is touched.
- `AITASK_BOARD_BENCH=1 python3 -m pytest tests/test_board_movement.py -v -k bench`
  produces the baseline table.
- §0's disambiguation **and** the §8 confirmation-checkpoint amendment are
  committed to the parent plan and reflected in the task file's Verification
  bullet **before** the benchmark runs; the baseline table, the options
  presented, and the user's recorded choice are appended after.
- On a missed gate, `git status` shows the working tree **unchanged** by the
  checkpoint, and no edit to `t1243_4` / `t1243_5` exists until the user has
  chosen.

## Risk

### Code-health risk: low

- One new test file; **zero production edits** — blast radius is
  `tests/test_board_movement.py` alone · severity: low · → mitigation: none needed.
- The flip table becomes a shared anchor t1243_3 and t1243_11 must edit, so a
  careless "make it pass" edit could erase the characterization · severity: low ·
  → mitigation: asserted exactly (never `assertGreater`), with an inline comment
  stating that a silent pass after a rewrite is a bug in the table.
- The harness is substantial for a test file (subprocess IPC, git fixture,
  instrumentation, benchmark) · severity: low · → mitigation: single file, no
  production dependency, and the mutation test keeps the oracle honest.

### Goal-achievement risk: medium

- The measurement can be invalid in ways that do not announce themselves —
  samples measuring rejected actions, `apply_filter` outside the timed region,
  double-counted nested spans, a fixture silently emptied by `_is_phantom_stub`,
  or lateral ping-pong drifting because the card did not start at the column
  bottom · severity: **high** · → mitigation: four per-sample validity invariants
  that **fail the run**, including an active-span stack that proves non-overlap
  rather than inferring it; an event-closed timed region; per-pair pre-state
  restoration assertions; non-board keys in the fixture; an asserted loaded-task
  set.
- **Harness overhead can swamp the signal**: `pilot.pause()` injects ≥ 20 ms of
  synthetic sleep per call, which would land in the wall-clock denominator and
  could falsely refute the 40 % premise · severity: **high** · → mitigation:
  `pause()` is excluded from the timed region by construction (closed on
  `asyncio.Event`s), leaving only real production latency in `e2e_i`; `defer_i`
  is measured as one non-overlapping interval and reported as diagnostic.
- **A mis-specified gate can be wrong in either direction** — subtracting
  deferral from the denominator would pass work that cannot meet its own target,
  and a per-component 40 % test would refute children whose combined removable
  cost clears it · severity: **high** · → mitigation: §0 pins one wall-clock
  denominator for both rules, keeps 40 % for the combined workstream only, and
  gates each child on its own combined removable cost at its own 30 % target —
  all committed before any observation.
- A leaked `TASK_DIR` in the shared pytest interpreter would point later tests
  and their subprocesses at a deleted temp tree · severity: medium ·
  → mitigation: `patch.dict` around the only parent-process mutation, with an
  explicit post-block restoration assertion; every other path passes `TASK_DIR`
  through `env=` to the child only.
- A count+hash oracle can pass a regression that writes the right files with
  wrong values · severity: **high** · → mitigation: §4's final-state, ordering,
  identity and non-board-survival assertions, with the expected order recomputed
  independently rather than taken from the board.
- Measuring the wrong git topology would attribute cost to the wrong span ·
  severity: medium · → mitigation: the fixture reproduces production branch mode
  (symlink + `.aitask-data` + relative `TASK_DIR`); both topologies are reported
  and the checkpoint uses the production one.
- The harness could read the real `aitasks/` tree in a full-suite run ·
  severity: medium · → mitigation: subprocess isolation **plus** the cwd seam,
  verified standalone and in-suite, with a read-only negative control that proves
  the in-process variant enumerates the real tree.
- The premise may be refuted, making t1243_4 / t1243_5 the wrong work ·
  severity: medium · → mitigation: a **planned branch** of the checkpoint, not a
  failure — per-axis rules are pre-registered and committed before any
  observation, each child's fate is decided by its own rule, and the disposition
  is chosen by the **user** at the §8 confirmation checkpoint rather than acted
  on automatically.
- A single benchmark run could otherwise trigger irreversible roadmap surgery
  (rewritten sibling tasks, discarded implementations) off one noisy number ·
  severity: medium · → mitigation: §8 forbids the agent from editing tasks or
  touching the working tree on a miss; it presents the data and the four options
  and waits, and the choice is non-skippable under `fast` / auto mode.
- The baseline is machine- and load-dependent, so t1243_14's comparison could be
  noise · severity: medium · → mitigation: p90 alongside median, every method
  parameter fixed and recorded, per-axis comparison, identical gated method re-run.

### Planned mitigations

No blocking pre-work mitigation tasks are needed. The one follow-up mitigation,
**t1243_14 `retrospective_benchmark`**, already exists as a sibling created at
decomposition time — no new mitigation task is created by this child.
