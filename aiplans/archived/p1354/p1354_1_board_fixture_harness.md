---
Task: t1354_1_board_fixture_harness.md
Parent Task: aitasks/t1354_speed_up_python_test_suite.md
Sibling Tasks: aitasks/t1354/t1354_2_migrate_remaining_board_tests.md, aitasks/t1354/t1354_3_parallel_test_lane.md, aitasks/t1354/t1354_4_retrospective_measure.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-07-31 13:38
---

# t1354_1 — Board fixture harness + migrate the two worst files (spike)

## Context

`bash tests/run_all_python_tests.sh` takes ~746s and the cost is concentrated:
the board TUI test modules `os.chdir(REPO_ROOT)` in `setUpClass` and boot the
real `KanbanApp` against the **live** `aitasks/` tree (213 parent cards today,
and growing every week). This child is the parent's deliberate spike: build the
shared fixture harness, prove full `KanbanApp` Pilot boots work against a temp
tree, and migrate the two worst files — which also fixes the two bugs folded
into the parent (t1346 / t1352).

Parent: `aitasks/t1354_speed_up_python_test_suite.md`, plan
`aiplans/p1354_speed_up_python_test_suite.md`.

## Verification of this plan against the current tree (2026-07-31)

Every claim was re-checked; all measurements are from this checkout
(`~/.aitask/venv`, Python 3.14).

**Confirmed unchanged:** `build_tree(root, cards, *, branch_mode=True,
settings=None)` at `tests/test_board_movement.py:121`; `_load_board_module` at
`tests/test_board_decref_doomed_attachments.py:36-52`; board constants at
`aitask_board.py:66-77`; `_is_phantom_stub` at `:921`; the production filter
`if not task_num: continue` at `:7271-7272`; `ByTrailTestBase.setUpClass` at
`tests/test_board_bytrail_view.py:71-82`; `WorkReportTestBase` at
`tests/test_board_work_report.py:46-57`; the failing assertion at `:483`;
`test_board_persistence_seam.py`'s import of the promoted helpers at `:66-69`.

**Line-reference corrections:** `_META_BASE` is at `test_board_movement.py:75-81`
(task said `:54-59`); `refresh_git_status` is `aitask_board.py:1062-1082` and
`refresh_lock_map` `:1084-1103` (task said `:1066-1069` / `:1084-1091`).

**The bug is live.** `test_board_work_report.py` fails right now:
`AssertionError: 157 != 158` at `:483`, 23 tests in **29.2s** (task recorded
25.9s — the tree grew). Trigger still on disk:
`aitasks/t_refresh_codeagent_suite_default_model_expectations.md`.

**Spike premise proven; the cwd question is now measured.** Full `KanbanApp` +
`run_test()` Pilot boots against a `TASK_DIR` fixture tree already work —
`OnDiskRefreshTests` (`test_board_bytrail_view.py:1006`) does it today.
Boot + one `pilot.pause()`, min of 3:

| variant | boot | pause | cards |
|---|---|---|---|
| live tree, cwd=`REPO_ROOT` | **2.437s** | 55.3ms | 213 |
| fixture, cwd=`REPO_ROOT`, absolute `TASK_DIR` | 0.620s | 22.9ms | 8 |
| fixture, **cwd=tree**, relative `TASK_DIR`, no git | **0.193s** | — | 8 |
| fixture, **cwd=tree**, relative `TASK_DIR`, with git | **0.190s** | — | 8 |

**Decision: chdir into the fixture tree, `TASK_DIR="aitasks"` (relative).** Do
*not* symlink `.aitask-scripts` into the tree — that re-enables the real
lock-script subprocess and hands back the 0.43s.

Two costs measured, both negligible, so per-test trees/modules are affordable:
`spec_from_file_location` module exec **0.115s cold / 0.011s warm**;
`build_tree` (incl. git init+add+commit) **0.005s**.

**Corrected expectation.** The task predicts "~10x on bytrail". Per boot the
measured ratio is 2.437 → 0.190 = **12.8x**, but a file's wall time also
contains non-boot work. With 57 `KanbanApp()` boots in
`test_board_bytrail_view.py`, ~128s of its 165.6s baseline is boot cost; the
realistic target is **~35-55s (3-5x)**. Record measured before/after — do not
assert a 10x AC, and do not use a timing ceiling as a regression guard.

**Scope the task under-counts:** `skipTest`-on-unhelpful-live-tree appears
**4x** in `test_board_work_report.py` (`:389`, `:406`, `:433`, `:461`) and
**2x** in `test_board_bytrail_view.py` (`:587`, `:784`) — all six become
unconditional. `_load_board_module` exists in **three** near-identical copies
(`test_board_decref_doomed_attachments.py:36`,
`test_board_bytrail_view.py:1034`, plus `test_board_movement.py`'s child
idiom); the harness absorbs them.

### Five review concerns — all verified valid, all addressed below

1. **Fixture contract / ghost resolution (high).** `load_local_project_name()`
   (`aitask_board.py:544-557`) reads `TASKS_DIR/metadata/project_config.yaml`;
   missing → `""` → `trail_ref_to_local_id` (`:560-569`) returns `None` → the
   entry becomes a `cross_repo` ghost. **`build_tree` writes no
   `project_config.yaml` and no child files at all.** Measured on a fixture
   tree with a trail doc referencing `aitasks#9000` and `aitasks#9000_1`:

   | fixture | `local_project` | TrailTaskCard | ghost |
   |---|---|---|---|
   | without `project_config.yaml` | `''` | **0** | **2** |
   | with `project:\n  name: aitasks` | `'aitasks'` | **2** | **0** |

   Without the fix every trail assertion in the migrated module would pass
   **vacuously against ghosts**. Addressed in step 2 (declarative topology) and
   step 4 (direct parent+child resolution assertion with a negative control).

2. **cwd-relative dependencies (high).** Confirmed and now bounded. Full
   inventory reachable from these tests: `DATA_WORKTREE` (`:71`) →
   `_task_git_cmd()` → `refresh_git_status`; `./.aitask-scripts/aitask_lock.sh
   --list` in `refresh_lock_map` (`:1084`); `ARTIFACT_SCRIPT` (`:490`) and
   `TRAIL_GATHER_SCRIPT` (`:491`) via `load_trail_blob` / `run_trail_drift` /
   `_trail_versions`; `CODEAGENT_SCRIPT` (`:74`), `CREATE_SCRIPT` (`:75`),
   `BRAINSTORM_TUI_SCRIPT` (`:76`); `agent_command_screen.py:999`
   (`aitask_skill_rerender.sh`); `sync_action_runner.py:76` (`_SYNC_SCRIPT`).
   Every one is wrapped in `except (…FileNotFoundError, OSError)`, so an absent
   script **degrades silently** and a test can pass through the fallback instead
   of the branch it names. Addressed in step 5a.

   **Corrected during implementation (review concern 6).** The planning probe
   reported "exactly one spawn: `git status`" because it cleared its spy after
   the first `pilot.pause()` — by which point `on_mount` →
   `refresh_board(refresh_locks=True)` had already run. Measured **per phase**,
   the real inventory is two:

   | phase | spawns |
   |---|---|
   | boot | `git -C .aitask-data status --porcelain -- aitasks/` (works) **+ `./.aitask-scripts/aitask_lock.sh --list` (ABSENT → degrades)** |
   | By-Trail entry + local refresh | `git -C .aitask-data status --porcelain -- aitasks/` |

   So every board boot on this harness runs with an empty `lock_map`. That is
   the accepted trade — staging the helper back costs the ~0.43s that cwd=tree
   buys — but it is now **asserted per phase**, not assumed.

3. **`TASK_DIR` must be the relative literal (medium).** `load_board_module`
   exports whatever string it is handed. Measured with a dirtied file in a
   branch-mode fixture: `TASK_DIR="aitasks"` → `is_modified` hits
   `['t9000_fixture.md']`; absolute `TASK_DIR` → git still reports
   `aitasks/t9000_fixture.md` but `is_modified` returns **`[]`** — the modified
   marker silently stops working. Addressed in step 2 (harness invariant) and
   step 3 (modified-marker assertion).

4. **Cleanup ordering (medium).** `addClassCleanup` is **LIFO** — verified:
   registering `FIRST` then `SECOND` executes `['SECOND', 'FIRST']`. So the
   tmpdir cleanup must be registered **first** and the chdir restore **second**,
   or the tree is removed while cwd is still inside it. A successful setup
   cannot prove this. Addressed in step 2 + a forced-failure test in step 3.

5. **Regression guard (medium).** Nothing mechanical stops either module
   reverting to `os.chdir(REPO_ROOT)` / a canonical `import aitask_board`.
   Addressed in step 6. **Note the trap:** under cwd=tree with
   `TASK_DIR="aitasks"` the synthetic module's `TASKS_DIR` *is* `Path("aitasks")`
   — identical to canonical. The guard must compare **resolved** paths.

## Steps

1. **Baseline.** Per-file wall time for both files
   (`python -m unittest discover -s tests -p <file>`). work_report already
   measured: **29.2s, 1 failure**. Measure bytrail at task start.

2. **Create `tests/lib/board_fixture.py`.** Imported flat per the established
   convention `sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))`
   (`tests/test_monitor_shadow_pick.py:47`); `tests/lib/` has no `__init__.py`.

   **Declarative fixture topology** — one spec object, not positional tuples,
   so every migrated test states what it needs:

   ```python
   FixtureTask(id="9000",   col="c0", idx=10, status="Ready")          # parent
   FixtureTask(id="9001",   col="c1", idx=10, status="Implementing")
   FixtureTask(id="9002",   col="c2", idx=10, status="Done")
   FixtureTask(id="9003",   col="c3", idx=10)
   FixtureTask(id="9004",   col="c4", idx=10)
   FixtureTask(id="9000_1", col="c0", idx=20)   # -> aitasks/t9000/t9000_1_*.md
   FixtureTask(id="9000_2", col="c1", idx=20)   # -> aitasks/t9000/t9000_2_*.md
   FixtureTask(filename="t_unparseable.md", col="c0", idx=99)   # numberless
   ```

   **The numberless task needs an explicit column and index** — measured: with
   `boardcol: c0` it lands in `c0` alongside the parseable tasks and the
   `:7271` drop fires (`get_column_tasks("c0")` = 4, `option_count` = 3);
   **without** board keys it lands in `'unordered'`, a different column from
   the one the work-report test targets, so the filter never runs and the file
   is merely present on disk. `c0` is deliberately the column the migrated
   work-report test focuses.

   with `project_name="aitasks"` written to
   `<tasks>/metadata/project_config.yaml` as `project:\n  name: aitasks\n`, and
   **no `artifacts:` frontmatter anywhere** so `discover_trails`
   (`aitask_board.py:808`) returns `[]` by construction. Child ids materialise
   at `TASKS_DIR/t<parent>/t<parent>_<child>_*.md` — the path
   `load_child_tasks` (`:940-948`) globs and `_build_active_trail_lanes`
   (`:7384-7392`) keys by `task_own_id`. Every task carries ≥1 non-board
   metadata key or `_is_phantom_stub` (`:921`) drops it and assertions pass
   vacuously.

   Surface:
   - `build_tree(...)` — moved from `test_board_movement.py:121` with
     `fixture_name`, `_fixture_text`, `_META_BASE`/`_META_ORDER`, `COLUMNS`,
     `snapshot`, `diff_snapshots`, `expected_nonboard`. **Two additions**:
     writes `project_config.yaml`, and materialises child tasks. Existing
     callers' behaviour must stay byte-identical (their differ depends on it) —
     if `project_config.yaml` would perturb `test_board_movement`'s snapshot
     allowlist, gate the two additions behind explicit parameters defaulting to
     the current behaviour for existing callers.
   - `load_board_module(task_dir, tag)` — the synthetic-module-name +
     `try/finally` env-restore pattern.
   - `FixtureBoardTestBase` / `boot_fixture_board(...)` owning the whole seam.
     **Invariant, asserted inside the harness, not left to callers:** cwd is
     the tree AND `TASK_DIR` is the relative literal `"aitasks"`. Reject an
     absolute path with a clear error (concern 3).
   - **Cleanup order (concern 4):** register tmpdir cleanup **first**, chdir
     restore **second**, so LIFO restores cwd before removing the tree; both via
     `addClassCleanup` registered immediately after the corresponding
     acquisition, so a mid-`setUpClass` failure cannot leak cwd into the
     single-process suite.
   - Docstring records: the **boot-mode vs patch-mode** rule (use
     `load_board_module` when booting an app — `mock.patch.object(aitask_board,
     "TASKS_DIR", …)` does *not* update derived constants `METADATA_FILE` /
     `TASK_TYPES_FILE` / `GATES_REGISTRY_FILE`, see
     `test_board_persistence_seam.py:19-33`); the cwd decision and its measured
     justification; and the cwd-relative dependency inventory from concern 2.

3. **Harness self-tests** (new, small — the harness is now load-bearing for
   t1354_2's bulk migration):
   - **Modified-marker assertion** (concern 3): dirty a fixture task after the
     fixture commit and assert `is_modified` reports it. Negative control:
     the same assertion under an absolute `TASK_DIR` must fail (measured: it
     returns `[]`).
   - **Forced-failure cleanup test** (concern 4): make `load_board_module`
     raise *after* the chdir, then assert the original cwd is restored **and**
     the temp tree is removed. A green setup cannot prove this path.
   - **Phantom-stub guard:** a board-keys-only fixture task loads zero tasks.

4. **Re-point existing importers, no logic change.**
   `test_board_movement.py` imports the promoted helpers (it re-execs itself as
   the child interpreter, so the `tests/lib` path insert must sit at module
   level, above the `--child` dispatch at `:1077`);
   `test_board_persistence_seam.py:66-69` updates its import site. Both stay
   green, including `IsolationNegativeControlTests` — which asserts the
   **canonical** `aitask_board.TASKS_DIR == Path("aitasks")` and that
   `TASK_DIR` is restored (the synthetic-module-name approach keeps both true).

5. **Migrate `test_board_bytrail_view.py`.** Replace `ByTrailTestBase`'s
   `os.chdir(REPO_ROOT)` + live `import aitask_board` (`:73-81`) with the
   harness, and fold `OnDiskRefreshTests`' private `_load_board` (`:1034-1051`)
   and its `chdir(REPO_ROOT)` (`:1022`) into it. The live repo's *absence* of
   `artifacts:` frontmatter was the implicit "no-trails fixture" — commented as
   such at `:504-505`; the fixture makes it explicit.
   `trail_schema.load_schema()` resolves `DEFAULT_SCHEMA_PATH` from `__file__`,
   so it is chdir-safe.

   **5a. Per-test cwd-dependency discipline (concerns 2 + 6).** Pinned by
   `FixtureCwdDependencyTests`, which asserts the boot spawn set **before** it
   resets its spy — clearing first would leave the boot path (the one every test
   in the file runs) entirely unguarded — then asserts the By-Trail phase
   separately. It also pins the *consequence* of the absent lock helper
   (`manager.lock_map == {}`); negative control: staging a working
   `aitask_lock.sh` into the fixture makes that assertion fail, proving it is
   not vacuous and that the helper is genuinely consulted at boot. For every migrated
   test, name the cwd-relative helper it reaches (inventory above) and either
   (a) stub it explicitly — most already do, via `patch.object(ab, …)` at
   `:766-771`, `:1883-1895` or `patch("subprocess.run")` at `:855/889/906/966/992`
   — or (b) stage the required read-only input in the fixture. Then **assert the
   intended branch was reached**: record spawned argv with a spy and assert the
   expected verb (as `ReadOnlyNegativeControlTests` already does at `:838-856`),
   so a `FileNotFoundError` fallback cannot masquerade as a pass. Any test whose
   assertion cannot distinguish "intended branch" from "helper absent" gets an
   explicit branch assertion added.

   **5b. Ghost-vs-real assertion (concern 1).** A direct test that a
   representative **parent** ref (`aitasks#9000`) and a representative **child**
   ref (`aitasks#9000_1`) each render as a real `TrailTaskCard` with
   `TrailGhostCard` count 0. Negative control: removing `project_config.yaml`
   flips both to ghosts (measured 2 real/0 ghost → 0 real/2 ghost), proving the
   assertion discriminates.

6. **Migrate `test_board_work_report.py`** and fix t1346/t1352:
   - `test_hidden_cards_still_listed` (`:448-486`): both sides of the equality
     from the same fixture moment. **No range-widening.**
   - All four `skipTest` sites become unconditional assertions.
   - The numberless `t_unparseable.md` sits in `c0` — the column the test
     focuses — so the production filter at `aitask_board.py:7271-7272` actually
     *runs*. Assert **both**: `option_count == len(parseable tasks in c0)`
     **and** `option_count != len(get_column_tasks("c0"))`. The second is what
     proves the drop fired; the equality alone is satisfied vacuously by a
     fixture with no unparseable file. Measured on the fixture: total 4,
     parseable 3, `option_count` 3.

7. **Structural regression guard (concern 5)** — narrow, scoped to exactly the
   two migrated modules (not all board tests: `test_board_persistence_seam.py`
   legitimately imports `aitask_board` canonically). Two parts:
   - **Structural:** AST scan of the two files asserting no `os.chdir(REPO_ROOT)`
     and no canonical `import aitask_board`.
   - **Isolation:** boot through the harness and assert
     `Path(module.TASKS_DIR).resolve()` is inside the fixture tree and **not**
     under `REPO_ROOT`. Comparing the unresolved value is useless — under
     cwd=tree it is `Path("aitasks")`, exactly like canonical.
   - **Negative control:** prove the guard fails when a `chdir(REPO_ROOT)` is
     reintroduced (mutate a source copy in memory / restore by undoing only the
     mutation, no `git checkout`).
   No timing ceiling — the measured before/after belongs in the plan record,
   not in a flaky assertion.

8. **Surface at Step 8b:** t1352's open sub-question — should the board /
   `ait ls` warn visibly about unparseable task filenames instead of silently
   dropping them? Propose as a standalone follow-up; do not bury it here.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` subset green for:
  `test_board_bytrail_view`, `test_board_work_report`, `test_board_movement`,
  `test_board_persistence_seam`, plus the new harness self-tests. Read only the
  last line (`PYTHON SUITE: PASSED|FAILED …`); mind `PIPESTATUS[0]` when piping.
- Per-file before/after wall times recorded here (work_report before: 29.2s /
  FAILED; bytrail before: measure at start).
- **Negative controls, each proven to fail before being trusted:** (a) empty the
  fixture's populated column → migrated `test_hidden_cards_still_listed` FAILS;
  (b) remove `project_config.yaml` → the ghost-vs-real assertion FAILS;
  (c) absolute `TASK_DIR` → the modified-marker assertion FAILS;
  (d) reintroduce `chdir(REPO_ROOT)` → the structural guard FAILS;
  (e) move the numberless task out of `c0` (or drop it) → the
  `option_count != total` drop assertion FAILS, proving the t1352 filter is
  genuinely exercised rather than incidentally satisfied.
- **Coverage check, per assertion:** confirm the fixture reproduces the *shape*
  each assertion needs (card count, column population, children, ghost/real
  split) rather than shrinking it away.
- Full suite green, or failures demonstrably pre-existing.

## Risk

### Code-health risk: medium
- Migrating ~66 assertions off the live tree can silently weaken coverage where
  a test depended on live-tree volume or shape · severity: medium · → mitigation:
  per-assertion coverage check + four proven-failing negative controls (in-plan,
  Verification)
- A cwd-relative helper absent under cwd=tree lets a test pass through a
  degrade/fallback branch instead of the one it names · severity: medium ·
  → mitigation: step 5a inventory + explicit branch assertions
- `chdir` mutates process-global cwd in a single-process suite; a leak between
  setup and teardown breaks every later module · severity: medium ·
  → mitigation: LIFO-ordered `addClassCleanup` + forced-failure test (steps 2, 3)
- Moving `build_tree` touches `test_board_movement`'s characterization/benchmark
  harness and the persistence-seam importer · severity: low · → mitigation:
  parameter-gated additions + both files re-run green (steps 2, 4)

### Goal-achievement risk: low
- The load-bearing assumption (full `KanbanApp` Pilot boot on a fixture tree) is
  measured before implementation, not assumed · severity: low
- Individual bytrail tests may depend on live-tree properties not yet
  enumerated; each is fixable by shaping the fixture · severity: low ·
  → mitigation: per-assertion coverage check (in-plan, Verification)

## Measured results

Per-file wall time, same machine, `python -m unittest discover -s tests -p <file>`:

| file | before | after | ratio |
|---|---|---|---|
| `test_board_bytrail_view.py` | **227.2s** (73 tests, OK) | **29.3s** (76 tests, OK) | **7.8x** |
| `test_board_work_report.py` | **29.2s** (23 tests, **FAILED**) | **4.7s** (23 tests, OK) | **6.2x** |
| `test_board_movement.py` | 12.0s | 12.0s | — (unchanged, re-pointed only) |
| `test_board_persistence_seam.py` | 0.57s | 0.57s | — (unchanged, re-pointed only) |
| `test_board_fixture_harness.py` | — | 0.56s (15 tests, new) | — |

Combined, the five files run in **46.0s in one interpreter** (161 tests, no cwd
or `TASK_DIR` leakage between modules) against a ~269s before. The bytrail
baseline came in at 227.2s rather than the task's recorded 165.6s — the live
tree grew between the two measurements, which is precisely the growth curve
this task exists to break.

The realized ratio beat the plan's 3-5x projection because the fixture also
cuts `pilot.pause()` (55.3ms → 22.9ms) across the file's many awaits, not just
the 57 boots.

**Full suite:** `PYTHON SUITE: PASSED (runner=unittest, exit=0)` — 2969 tests in
**577.9s**, against the ~746s the task recorded. Every negative control was run
and observed to fail (see Verification); the four permanent ones ship as
passing tests that assert the broken behaviour, and the two one-off ones were
demonstrated by subclassing the real test with a reshaped fixture rather than
mutating any file.

## Final Implementation Notes

- **Actual work done:** Built `tests/lib/board_fixture.py` (declarative
  `FixtureTask` topology, `build_fixture_tree`, `load_board_module`,
  `enter_fixture_tree`, `FixtureBoardTestBase`, plus the `build_tree`/`snapshot`/
  `diff_snapshots` vocabulary promoted verbatim from `test_board_movement.py`).
  Added `tests/test_board_fixture_harness.py` (16 self-tests incl. the structural
  regression guard). Migrated `test_board_bytrail_view.py` and
  `test_board_work_report.py` onto the harness; re-pointed
  `test_board_movement.py` and `test_board_persistence_seam.py` at the promoted
  helpers with no behavior change. All six `skipTest`-on-live-tree sites became
  unconditional assertions. Fixed t1346 + t1352.

- **Deviations from plan:** Three, all recorded above in place.
  1. The plan's cwd-dependency inventory said a boot + By-Trail entry spawns
     "exactly one" subprocess. Wrong — the planning probe cleared its spy after
     the first `pilot.pause()`, hiding everything `on_mount` had already done.
     The real boot also runs `./.aitask-scripts/aitask_lock.sh --list`, which is
     absent under the fixture and degrades silently. The guard now asserts the
     boot set **before** resetting, and pins `lock_map == {}`.
  2. `build_tree` gained `project_name=None` rather than unconditionally writing
     `project_config.yaml`, so `test_board_movement`'s byte differ sees exactly
     the file set it always saw. The declarative `build_fixture_tree` defaults it
     to `"aitasks"` instead.
  3. Speedup exceeded the plan's 3-5x projection (7.8x on bytrail) because the
     fixture also halves `pilot.pause()` (55.3ms → 22.9ms), not just boots.

- **Issues encountered:** The first cwd guard asserted `argv[:2] == ["git",
  "status"]` and failed — branch mode routes through `git -C .aitask-data`,
  which is exactly the production topology the fixture reproduces. Relaxed to
  assert `status` + `--porcelain` are present.

- **Key decisions:**
  - **cwd=fixture tree, `TASK_DIR="aitasks"` relative.** Measured 0.190s/boot vs
    0.620s for the cwd=REPO_ROOT idiom and 2.437s live. Deliberately did NOT
    symlink `.aitask-scripts` into the tree; the resulting empty `lock_map` is
    asserted rather than left implicit.
  - **Guard is structural (AST), never a timing ceiling** — a wall-clock
    assertion would be flaky under load and would not say why it regressed.
  - **Every negative control was executed and observed to fail**, not assumed:
    absolute `TASK_DIR` loses the modified marker; a missing
    `project_config.yaml` turns both trail refs into ghosts; a reintroduced
    `chdir`/canonical import trips the AST guard (and a mention in a string does
    not); emptying `c0` breaks the work-report flow; removing the numberless file
    trips `1 == 1 : the fixture must keep an unparseable filename in this
    column`; staging a working `aitask_lock.sh` breaks the `lock_map == {}` pin.

- **Upstream defects identified:** None.

- **Follow-up created (Step 8b):** **t1364**
  (`aitasks/t1364_warn_on_unparseable_task_filenames.md`) — t1352's open product
  question: should the board / `ait ls` warn visibly about unparseable task
  filenames instead of silently dropping them? Deliberately kept out of this
  perf change, as the parent plan recommended. Note that
  `test_board_work_report.py` now *pins* the current drop behaviour, so t1364
  must update that test intentionally rather than incidentally.

- **Notes for sibling tasks:**
  - **t1354_2** (migrate the remaining ~9 live-tree board modules) is now mostly
    mechanical: subclass `bf.FixtureBoardTestBase`, delete the
    `chdir(REPO_ROOT)` + canonical `import aitask_board`, and add the module's
    name to `MIGRATED_MODULES` in `tests/test_board_fixture_harness.py` so the
    structural guard covers it. Reshape the tree per class via `FIXTURE_TASKS`;
    use `enter_fixture_tree(self.addCleanup, ...)` for tests that MUTATE task
    files (a class-level tree is shared).
  - **Read the `board_fixture` module docstring first.** Two traps are only
    documented there: `project_config.yaml` is mandatory for any trail test (its
    absence turns every `aitasks#<id>` into a silent ghost, and nothing raises),
    and every fixture task needs ≥1 non-board metadata key or
    `_is_phantom_stub` drops it and the whole class passes vacuously.
  - **Discoverability question left open for t1354_2:** the harness is currently
    documented only in its own docstring. If t1354_2 finds that insufficient
    while migrating 9 modules, a pointer in `aidocs/framework/tui_conventions.md`
    would be the natural home — deliberately not added here, as it was outside
    this task's approved scope.
  - **t1354_3** (parallel lane): the harness is xdist-safe per file (each class
    gets its own tmpdir), but it **chdirs the process**, so `--dist loadfile` is
    mandatory — splitting one file's classes across workers is fine (separate
    processes), but never run these classes in threads within one process.
  - Suite is now 577.9s; `test_syncer_rows.py` (124s) is the next-largest single
    file and has no live-tree coupling, so it needs its own analysis.

## Step 9 (Post-Implementation)

Current-branch mode: no worktree to remove. Run the declared gates
(`risk_evaluated`) via the orchestrator, then archive with
`./.aitask-scripts/aitask_archive.sh 1354_1`.
