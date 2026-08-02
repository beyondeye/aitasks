---
Task: t1354_2_migrate_remaining_board_tests.md
Parent Task: aitasks/t1354_speed_up_python_test_suite.md
Sibling Tasks: aitasks/t1354/t1354_3_parallel_test_lane.md, aitasks/t1354/t1354_4_retrospective_measure.md
Archived Sibling Plans: aiplans/archived/p1354/p1354_1_board_fixture_harness.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-02 09:56
---

# t1354_2 — Migrate remaining live-tree board tests + regression guard

## Context

`tests/run_all_python_tests.sh` sits on every task's verification path. Its cost
is concentrated in board TUI modules that `os.chdir(REPO_ROOT)` in `setUpClass`
and boot the real `KanbanApp` against the **live** `aitasks/` tree (213+ parent
cards, growing weekly) — so the suite gets slower every week and is coupled to
whatever happens to be on disk.

Sibling **t1354_1** (archived) built the shared harness `tests/lib/board_fixture.py`
and proved the pattern on the two worst files: `test_board_bytrail_view.py`
227.2s → 29.3s (7.8x) and `test_board_work_report.py` 29.2s/**FAILED** → 4.7s/OK.
Full suite went 746s → 577.9s.

This child migrates the **remaining** live-tree board modules onto that harness
and replaces t1354_1's deliberately narrow regression guard with one that
prevents the coupling from creeping back into *any* board test — including files
that don't exist yet.

## Plan verification (2026-08-02) — what changed vs. the task text

Every claim in the task was re-checked against this checkout. Three corrections:

### 1. The file list was incomplete — 15 modules, not 9

A full sweep (`grep -rn chdir tests/*.py`, cross-checked for
`TASK_DIR`/`TASKS_DIR`/`mkdtemp`/`board_fixture` in the same module) found **six
more** live-tree-coupled board modules the 2026-07-31 enumeration missed. They
are not new files — `git log --diff-filter=A -- 'tests/test_*.py'` shows no test
file added since 2026-07-31; they were simply never listed.

They are cheap (0–2 app boots) so they contribute little perf, but they are the
reason a glob-scoped guard cannot be written without deciding their fate.
**User decision (2026-08-02): migrate all 15, so the guard's allowlist carries no
known-debt entries.**

### 2. Measured baseline (2026-08-02, `~/.aitask/venv` Python 3.14)

`python -m unittest discover -s tests -p <file>`, one file per interpreter.
Times are unittest's own `Ran N tests in …` (not wall clock).

| file | time | tests | `KanbanApp()` boots | `pilot.pause()` |
|---|---|---|---|---|
| `test_board_filter_row_layout.py` | **38.8s** | 12 | 10 | 1 |
| `test_board_view_filter.py` | **38.2s** | 12 | 8 | 22 |
| `test_board_detail_collapsible.py` | **37.3s** | 12 | 11 | 27 |
| `test_board_topic_view.py` | **30.7s** | 6 | 6 | 13 |
| `test_board_scroll_focus_jump.py` | **22.6s** | 10 | 10 | 3 |
| `test_board_toggle_children_gate.py` | **19.0s** | 3 | 3 | 9 |
| `test_board_empty_column_focus.py` | **15.2s** | 12 | 12 | 1 |
| `test_board_detail_nested_actions.py` | **11.5s** | 4 | 3 | 13 |
| `test_board_detail_arrow_nav.py` | **8.6s** | 3 | 3 | 9 |
| *(subtotal — the 9 listed)* | **221.9s** | 74 | 66 | 98 |
| `test_board_inflight_view.py` † | 5.5s | 9 | 2 | 6 |
| `test_board_picker_tab_nav.py` † | 5.4s | 2 | 2 | 5 |
| `test_board_footer_visibility.py` † | 4.1s | 2 | 2 | 2 |
| `test_board_topic_group.py` † | 0.18s | 30 | 0 | 0 |
| `test_board_dialog_subprocess_degrade.py` † | 0.16s | 9 | 0 | 0 |
| `test_board_dialog_run_dispatch.py` † | 0.13s | 15 | 0 | 0 |
| *(subtotal — the 6 newly found)* | **15.5s** | 67 | 6 | 13 |
| **total** | **237.4s** | **141** | **72** | **111** |

† newly found; not in the task's list. All 15 currently pass.

**Expectation, not a gate.** t1354_1 realized 7.8x where per-boot cost alone
predicted ~3-5x (the fixture also halves `pilot.pause()`: 55.3ms → 22.9ms).
Applying its realized per-boot saving (~3.5s) to 72 boots covers essentially the
whole 237s, so the honest projection is **~35-60s (4-6x)**. Record measured
before/after in this plan — **do not assert a timing ceiling** (flaky under load,
and it would not say *why* it regressed). This repeats t1354_1's explicit
decision.

### 3. A structural guard already exists — extend it, don't add a second one

The task says "add the regression guard (new `tests/test_board_fixture_guard.py`)".
That would **duplicate** `MigratedModuleGuardTests` at
`tests/test_board_fixture_harness.py:267-305`, which already ships an AST scanner
(`_live_tree_couplings`, `:243-264`), a `MIGRATED_MODULES` tuple (`:234-240`) and
an in-memory negative control. t1354_1's own hand-off notes say to *extend*
`MIGRATED_MODULES`.

**Deviation from the task text, made explicit:** no new `test_board_fixture_guard.py`.
The guard is reworked in place in `tests/test_board_fixture_harness.py` — one
guard, one home. Rationale below.

### 4. Dropped from scope: the two "optional" live-metadata readers

The task offers `tests/test_settings_brainstorm_descriptions.py:27` and
`tests/test_profile_editor_shadow_tier.py:150` "only if cheap". Verified: neither
chdirs or boots a board; both are **deliberate guards on real shipped config**
(`aitasks/metadata/codeagent_config.json`; `seed/profiles/*.yaml` vs
`aitasks/metadata/profiles/*.yaml`). Migrating them off live data would *destroy
the property they test*, and they cost ~0s. **Not migrated, by design.**

## Harness API (pinned from `tests/lib/board_fixture.py`, read at plan time)

- `class FixtureBoardTestBase` — a **mixin**, not a TestCase. Subclass as
  `class X(bf.FixtureBoardTestBase, unittest.TestCase)`. Class attrs:
  `FIXTURE_TASKS` (default `DEFAULT_TOPOLOGY`), `FIXTURE_SETTINGS`,
  `FIXTURE_PROJECT_NAME`. Exposes **`self.ab`** (board module — *not* `self.board`),
  **`self.tree`** (also the process cwd), `self.tasks_dir`.
- `bf.enter_fixture_tree(add_cleanup, *, tasks_spec=…, tag=…, project_name=…, …)`
  → `(tree, module)` — for tests that **mutate** task files (class tree is shared);
  pass `self.addCleanup`.
- `bf.FixtureTask(task_id, col, idx, status, filename, slug, extra)` — `extra`
  carries arbitrary frontmatter (`anchor`, `issue`, `depends`, …). Child ids use
  `"9000_1"` → `aitasks/t9000/t9000_1_<slug>.md`.
- `bf.DEFAULT_TOPOLOGY` — 5 parents `c0..c4` (t9001 `Implementing`, t9002 `Done`),
  2 children of t9000, plus `t_unparseable.md` in `c0`.

**Traps the docstring records (all load-bearing here):**
1. `TASK_DIR` must be the relative literal `"aitasks"` with cwd inside the tree —
   an absolute value silently zeroes `is_modified`. `load_board_module` rejects it.
2. Every fixture task needs ≥1 non-board metadata key or `_is_phantom_stub`
   (`aitask_board.py:921`) drops it and assertions pass **vacuously**.
3. `project_config.yaml` (`project.name`) is mandatory for trail refs.
4. **`lock_map` is always empty** under the fixture — `./.aitask-scripts/aitask_lock.sh`
   does not exist at the fixture cwd and the call degrades silently. Deliberate
   (staging it back costs ~0.43s/boot). Busy-ness must come from
   `status: Implementing` or from an entry the test **injects** into
   `manager.lock_map` itself (which works identically on the fixture — see
   `test_board_view_filter.py:275,304`), never from the absent helper.
   The same silent-degrade hazard applies to seven other helpers — see Step 2b.
5. Cleanup is LIFO: tmpdir registered first, chdir-restore second.

## Steps

### Step 1 — Additive fixture topologies (do **not** touch `DEFAULT_TOPOLOGY`)

`DEFAULT_TOPOLOGY` is pinned by two already-green files: `test_board_work_report.py`
asserts exact `c0` counts (`option_count == 3` vs 4 column tasks — the t1352 drop
proof), and `test_board_movement.py` byte-differs the produced file set. Mutating
it would silently break both. Add **new** names to `tests/lib/board_fixture.py`:

- `RICH_TOPOLOGY` — `DEFAULT_TOPOLOGY`'s shape plus the metadata the migrated
  assertions need: ≥2 distinct `anchor` values with ≥1 card each (topic lanes),
  ≥2 tasks carrying `issue:` (the git view-set), a `depends:` edge between two
  parents, and a busy child (`status: Implementing`).
- `wide_topology(n_parents, *, with_children=False)` — generator for the
  volume-dependent files. **`test_board_scroll_focus_jump.py` needs 40 parents**
  (`N_TALL = 30`, `N_SIDE = 10` at `:47-48`); shrinking it below that would trade
  a `skipTest` for a vacuous pass, which is the exact failure mode this task
  exists to remove.

### Step 2 — Migrate the 15 modules, one file per reviewable step

Mechanical core, per file: delete `os.chdir(REPO_ROOT)` / `tearDownClass` restore
and the canonical `import aitask_board`; subclass `bf.FixtureBoardTestBase`;
replace module-level board references with `self.ab`; add
`sys.path.insert(0, str(REPO_ROOT / "tests" / "lib"))` + `import board_fixture as bf`.

Every `skipTest`-on-unhelpful-live-tree becomes an **unconditional assertion**
(≈20 sites across the 9 hot files).

### Step 2a — Fixture facts: declared **and asserted**, per module

"Check every assertion" is not an auditable deliverable, and a module that
silently gets an underspecified fixture passes trivially — exactly the failure
the old `skipTest`s used to make visible. So each module's fixture requirements
are written as an **executable precondition test** (`test_fixture_facts`) that
runs before its behavioral checks and asserts the facts on the booted board.
An underspecified fixture then fails **loudly and by name**, and the matrix below
is auditable because it is code, not prose.

| module | required fixture facts (asserted in `test_fixture_facts`) |
|---|---|
| `test_board_scroll_focus_jump.py` | **≥40 parents** (`N_TALL=30 + N_SIDE=10`, `:47-48`; skip at `:96`) → `wide_topology(40)` |
| `test_board_empty_column_focus.py` | ≥4 parents **and** ≥1 parent with ≥1 child (`:95`, `:101`) |
| `test_board_topic_view.py` | ≥2 distinct `anchor` lanes, each with ≥1 card (`:65`, `:120`, `:155`) |
| `test_board_toggle_children_gate.py` | ≥1 parent card with children, clickable in the bytopic view (`:89`, `:134`, `:158`) |
| `test_board_view_filter.py` | ≥1 task with `issue:`/`pull_request:` (`_git_visible_set`, `aitask_board.py:6426`); ≥1 `status: Implementing`; ≥1 parent-with-children where **no** child is busy (`:299`) |
| `test_board_detail_collapsible.py`, `_nested_actions.py`, `_arrow_nav.py` | ≥2 parents + ≥1 `depends:` edge between them (`:120`, `:151`) |
| `test_board_filter_row_layout.py`, `test_board_footer_visibility.py`, `test_board_picker_tab_nav.py` | ≥1 card in ≥2 columns (layout/nav only) |
| `test_board_inflight_view.py` | ≥1 `status: Implementing` with a gate ledger |
| `test_board_topic_group.py`, both `dialog_*` | **0 boots** — chdir+import swap only; no topology requirement |

Every fact in this table is paired with a shrink-and-fail control (Step 4.6). A
fact with no control that can break it gets deleted, not kept.

### Step 2b — Per-module external-helper audit (mandatory, before each migration)

The fixture deliberately omits `.aitask-scripts`, and the harness docstring
records **eight** cwd-relative helpers that degrade *silently* (each wrapped in
`except (…FileNotFoundError, OSError)`) — not just `aitask_lock.sh`, but
`ARTIFACT_SCRIPT`, `TRAIL_GATHER_SCRIPT`, `CODEAGENT_SCRIPT`, `CREATE_SCRIPT`,
`BRAINSTORM_TUI_SCRIPT`, `agent_command_screen.py:999`
(`aitask_skill_rerender.sh`) and `sync_action_runner.py:76`. A migrated test can
therefore take a missing-helper fallback and pass **for the wrong reason**.
t1354_1 did this audit for one module (its step 5a); it must be repeated **per
module** here.

For each module, before migrating it: enumerate the external helpers its tested
paths reach, then for each one either **(a)** stub it explicitly
(`patch.object(self.ab, …)`) or **(b)** stage the required read-only input in the
fixture — and in both cases **assert the intended call/branch was reached**
(record spawned argv with a spy and assert the expected verb), so a
`FileNotFoundError` fallback cannot masquerade as a pass. Any test whose assertion
cannot distinguish "intended branch" from "helper absent" gets an explicit branch
assertion added. The three subprocess-centric modules are the highest risk and are
audited first: `test_board_dialog_run_dispatch.py` (patches `ab.subprocess.call`,
`:236-267`), `test_board_dialog_subprocess_degrade.py` (patches
`ab.subprocess.run` with exception `side_effect`s, `:142/162/296` — its whole
subject *is* the degrade path, so a fixture-induced degrade would be
indistinguishable from the one under test), and `test_board_inflight_view.py`.

**Hard blocker found at plan time — string-target patches.** The harness loads
the board under a **synthetic module name**
(`aitask_board_fixture_<tag>_<id>`), so `mock.patch("aitask_board.<attr>")`
patches the **canonical** module — a *different object* from `self.ab` — and the
code under test runs **unpatched**. Three such sites exist, all in
`tests/test_board_inflight_view.py:181-183`:

```python
with patch("aitask_board._current_tmux_session", return_value="aitasks"), \
        patch("aitask_board.find_window_by_name", return_value=("aitasks", "2")), \
        patch("aitask_board.subprocess.Popen") as popen:
```

Left as-is, the first two would silently miss and the test would invoke the
**real** tmux helpers. All string targets must become
`patch.object(self.ab, "_current_tmux_session", …)` etc. (Note
`patch("aitask_board.subprocess.Popen")` would keep "working" by accident —
`subprocess` is a shared module object — which is precisely why this must be
fixed deliberately rather than discovered by a green run.) Grep for
`patch("aitask_board` / `patch('aitask_board` in each module before migrating it;
verified today the count across all 15 is exactly these 3.

### Step 3 — Rework the guard in `tests/test_board_fixture_harness.py` — **fail-closed**

The task promises to catch `chdir(REPO_ROOT)` "**or equivalent**". An
argument-matching rule cannot deliver that: `os.chdir(str(REPO_ROOT))`,
`os.chdir(REPO_ROOT.resolve())`, `root = REPO_ROOT; os.chdir(root)` and
`import os as _os; _os.chdir(REPO_ROOT)` all reach the live tree while evading a
literal match. **Verified: the existing scanner is already evadable** — its rule
is an exact string match, `if func in ("os.chdir", "chdir")`
(`test_board_fixture_harness.py:257`), so an aliased `os` module slips through
today, and `self.addCleanup(os.chdir, original)` is a *reference*, not an
`ast.Call`, so it is not seen at all.

So the rule is **inverted to deny-by-default** rather than made cleverer. No
argument analysis, nothing to evade:

- **Rule:** in every globbed module, flag **any** chdir — matched by *suffix* on
  the unparsed callee (`chdir` or `*.chdir`, so `_os.chdir` / `pathlib.os.chdir`
  are caught), **plus** bare `os.chdir` **references** passed as values
  (`addCleanup(os.chdir, …)`, `map(os.chdir, …)`), **plus** `from os import chdir`
  imports — and flag any canonical `import aitask_board` / `from aitask_board import`.
- A module that legitimately chdirs must have each such **expression** pinned in
  the allowlist with a reason (see below — the exemption is per-expression, never
  per-module). Unknown/novel forms therefore fail **loudly**, not silently.

**Tier 2 (stricter, unchanged rule) still applies to the migrated set**:
`MIGRATED_MODULES` grows 2 → 17. `test_board_movement.py` and
`test_board_persistence_seam.py` stay **out** — on the fixture but importing the
board canonically on purpose (patch mode) — while the sweep still covers them
(neither chdirs).

**The allowlist has two entries, and each exempts specific chdir *expressions* —
never a whole module.** A module-level exemption would re-open the hole inside the
exempted files: a future accidental `os.chdir(REPO_ROOT)` in either of them would
be waved through by the very mechanism meant to catch it. So the allowlist maps
module → the exact set of permitted unparsed expressions (verified on disk at plan
time), and **anything else in that module is still flagged**:

```python
CHDIR_ALLOWED = {
    # the harness's own tests: chdir into fixture trees / a bare tmpdir
    "test_board_fixture_harness.py": frozenset({
        "os.chdir(tree)",                        # :51, :89, :206
        "os.chdir(tmp.name)",                    # :100
        "self.addCleanup(os.chdir, original)",   # :52, :90, :101, :207 (reference form)
    }),
    # chdirs into its own TemporaryDirectory, never REPO_ROOT
    "test_board_refresh_degrade.py": frozenset({
        "os.chdir(cls._tmp.name)",               # :88
        "os.chdir(cls._cwd)",                    # :92, :98
    }),
}
```

For the **reference form**, the scanner records the *enclosing call*
(`self.addCleanup(os.chdir, original)`), not the bare `os.chdir` — otherwise
permitting the bare reference would also permit
`self.addCleanup(os.chdir, REPO_ROOT)`.

Consequence, accepted: renaming a local in one of these two files trips the guard.
That is a loud one-line fix, and the failure message must say so ("expression not
in `CHDIR_ALLOWED[<module>]` — update the pinned set if this chdir is still
fixture-local"). Both entries are load-bearing: removing either makes the sweep
fail (Step 4.3), and neither can ever admit a `REPO_ROOT` chdir (Step 4.4).

**Documented policy boundary (the deliberately narrow part).** The guard prevents
the *chdir + canonical-import* coupling. It does **not** claim to catch every
conceivable route to live data — notably `tests/test_board_header_row_live.py`
reaches the real repo through tmux's own `-c str(REPO_ROOT)` (`:76`), by design
and with a per-PID socket (`:40`). Verified it has **no chdir and no
`aitask_board` import**, so it needs no allowlist entry; a comment in the guard
records that it is out of scope *by policy*, not by oversight — so a future
reader does not mistake its absence for coverage.

### Step 4 — Negative controls (each must be observed failing before it is trusted)

All synthetic modules are written into the test's **own tmpdir**. Never
revert/mutate a real test file on disk to demonstrate a guard.

1. **Equivalent-form matrix — the core of the "or equivalent" promise.** One
   synthetic module per form, each asserted flagged **with the expected identity**
   (module name + finding text), not merely "something was flagged":

   | # | form |
   |---|---|
   | a | `os.chdir(REPO_ROOT)` |
   | b | `os.chdir(str(REPO_ROOT))` |
   | c | `os.chdir(REPO_ROOT.resolve())` |
   | d | `root = REPO_ROOT` then `os.chdir(root)` |
   | e | `import os as _os` then `_os.chdir(REPO_ROOT)` |
   | f | `from os import chdir` then `chdir(REPO_ROOT)` |
   | g | `self.addCleanup(os.chdir, REPO_ROOT)` (reference, not a call) |
   | h | `import aitask_board` / `from aitask_board import KanbanApp` |

   Forms (b)–(g) are precisely the ones a literal-match rule would miss; (e) and
   (g) evade the *current* scanner and are the regression proof for this step.
2. **Structural, not substring:** a module mentioning `os.chdir(REPO_ROOT)` only
   inside a docstring/comment/string constant must **not** be flagged (keeps
   t1354_1's existing case).
3. **Allowlist is load-bearing:** re-run the sweep with each of the two
   `CHDIR_ALLOWED` entries removed from a *local copy*; each removal must make the
   sweep fail, naming that module. An allowlist entry no control can trip is a
   decorative lie.
4. **An exemption cannot hide a `REPO_ROOT` chdir (closes the last hole).** For
   **each** allowlisted module, take its real source, append
   `os.chdir(REPO_ROOT)` (and separately `self.addCleanup(os.chdir, REPO_ROOT)`)
   in memory, and assert the sweep **still flags it** — proving the exemption is
   scoped to the pinned expressions and not to the module. Also assert the
   converse: each pinned expression, on its own, is **not** flagged (so the
   exemption is real and the control is not passing for the trivial reason that
   everything is flagged).
5. **Tier-2 still fires:** keep t1354_1's in-memory mutation control, extended to
   assert the expected finding string.
6. **Fixture-shape controls — one per non-default topology requirement**, not
   just the three obvious ones. For **every** module whose `FIXTURE_TASKS` differs
   from `DEFAULT_TOPOLOGY` (Step 2a matrix), shrink the differing fact in a
   throwaway subclass and observe the migrated assertion **fail**. If shrinking a
   fact does not break anything, that fact was not actually needed — delete it
   from the module's declared requirements rather than leaving an unexercised claim.

### Step 5 — Measure and record (**suite wall clock is the primary number**)

Per-file `unittest` durations are diagnostics, not the goal. The task's goal is
the speed of the verification path, so the **primary** measurement is
`bash tests/run_all_python_tests.sh` **wall clock, same machine, one denominator**
— per-file times can improve while suite-level startup, ordering or shared-state
costs regress, and only the suite number would show that.

1. **Before**, measured at implementation start (do **not** reuse t1354_1's
   577.9s from 2026-07-31 — the tree has grown since):
   ```bash
   time bash tests/run_all_python_tests.sh
   ```
   Record real/user/sys, the test count, and the verdict line.
2. **After**, identical invocation, same machine, no other load. Record the same
   fields.
3. Record the per-file before/after table for all 15 (the "before" column is the
   2026-08-02 baseline above).
4. **Account for the delta explicitly.** The 15 modules are projected to fall
   237.4s → ~35-60s, i.e. a suite saving of **~180-200s**. If the observed
   suite-level saving differs materially from the sum of the per-file savings,
   say so and explain where the difference went (interpreter startup amortization,
   ordering, shared state) rather than reporting only the flattering number. A
   miss is recorded and presented — it is not a gate and must not be hidden.
5. Note the new binding constraint (largest remaining single file) for t1354_4.

## Verification

- All 15 migrated files green individually **and** in one interpreter (no cwd or
  `TASK_DIR` leakage between modules — t1354_1 proved 5 files coexist).
- Every module's `test_fixture_facts` precondition green (Step 2a), and every
  declared fact paired with a shrink-and-fail control observed failing (Step 4.6).
- Step 2b helper audit completed **per module**, with an explicit branch/verb
  assertion anywhere a tested path reaches a cwd-relative helper; zero remaining
  `patch("aitask_board…")` string targets across the 15.
- `tests/test_board_fixture_harness.py` green: the fail-closed sweep passes on the
  real tree with exactly the two justified `CHDIR_ALLOWED` entries; **all eight
  equivalent-form controls (Step 4.1 a–h) observed flagging**, both allowlist
  removals (Step 4.3) observed failing, and an injected `os.chdir(REPO_ROOT)` in
  **each** allowlisted module observed still flagged (Step 4.4) — so no exemption
  is module-wide. All observed before any of it is trusted.
- `test_board_movement.py` and `test_board_persistence_seam.py` unchanged and
  green (they import the promoted helpers; `DEFAULT_TOPOLOGY` untouched).
- Full suite green: `bash tests/run_all_python_tests.sh` → read **only** the last
  line (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); mind `${PIPESTATUS[0]}`
  when piping — the banner is on stderr but the exit status is not.
- **Suite wall clock recorded before and after** (Step 5), same machine, one
  denominator, with the delta accounted for against the ~180-200s projected saving.

## Risk

### Code-health risk: medium
- Migrating ~141 tests across 15 files can silently weaken coverage where an
  assertion depended on live-tree volume or shape (40-parent scroll case, topic
  lanes, git/issue set, parent-with-children) · severity: medium · → mitigation:
  fixture facts declared **and asserted** as an executable `test_fixture_facts`
  precondition per module (Step 2a) — prose "check every assertion" is not
  auditable, a failing precondition is
- ~20 `skipTest` guards become unconditional; a wrongly-shaped fixture converts a
  visible skip into a **vacuous pass** rather than a failure · severity: medium ·
  → mitigation: a shrink-and-observe-failure control for **every** declared fact,
  not a sampled three (Step 4.6); a fact no control can break is deleted
- A migrated test can pass by taking an unintended **missing-helper fallback**
  instead of the branch it names — the fixture omits `.aitask-scripts` and eight
  cwd-relative helpers degrade silently; the two `dialog_*` modules test degrade
  behavior itself, so a fixture-induced degrade is indistinguishable from the one
  under test. Confirmed live instance: `test_board_inflight_view.py:181-183`
  patches by string target on the canonical module and would miss entirely under
  the synthetic module name, invoking the real tmux helpers · severity: medium ·
  → mitigation: per-module helper audit with explicit stubbing + assert-the-verb-
  was-reached (Step 2b), string targets converted to `patch.object(self.ab, …)`
- Editing the shared `tests/lib/board_fixture.py` touches 4 already-green files
  (`bytrail_view`, `work_report`, `movement`, `persistence_seam`), two of which
  pin `DEFAULT_TOPOLOGY` byte-for-byte, and the contracts those files rely on
  exist only in one module docstring · severity: medium · → mitigation:
  additive-only topologies, `DEFAULT_TOPOLOGY` never modified (Step 1); all four
  re-run green (Verification); + `board_fixture_harness_docs`
- The guard is deliberately **fail-closed** (any chdir is a finding), so a
  legitimate new tmpdir-chdir module turns the suite red until allowlisted, and a
  lazily-grown allowlist would quietly restore the original hole · severity: low ·
  → mitigation: accepted by design — a loud false positive is recoverable, a
  silent miss is not; each entry needs a written reason and is proven
  load-bearing by a removal control (Step 4.3), so a decorative entry cannot survive
- The guard cannot claim to catch *every* route to live data (e.g. tmux `-c`,
  absolute `TASK_DIR`), so its coverage could be over-read · severity: low ·
  → mitigation: policy boundary stated in the guard itself, naming
  `test_board_header_row_live.py` as out of scope by policy rather than oversight
  (Step 3)
- `lock_map` is unconditionally empty under the harness, so a migrated test that
  sourced busy-ness from a *real* lock would pass for the wrong reason ·
  severity: low (checked: none do — `test_board_view_filter.py:275,304` and
  `test_board_inflight_view.py` **write** entries into `manager.lock_map`
  directly, which behaves identically on the fixture, so no lock coverage is
  lost) · → mitigation: busy-ness must come from an injected `lock_map` entry or
  `status: Implementing`, never from the absent helper — called out per-file in
  Step 2

### Goal-achievement risk: low
- The load-bearing assumption (full `KanbanApp` Pilot boot on a fixture tree) is
  already **measured and shipped** by t1354_1, not assumed · severity: low
- Per-file times can improve while the **suite** — the actual verification path
  this task exists to speed up — regresses through startup, ordering or
  shared-state costs, making a per-file-only report misleading · severity: low ·
  → mitigation: suite wall clock is the primary recorded number, before **and**
  after, with the delta reconciled against the summed per-file saving (Step 5)
- Scope grew 9 → 15 files during verification; further unlisted coupling would
  weaken the guard's completeness claim · severity: low · → mitigation: tier-1
  glob is exhaustive over `tests/test_board_*.py` by construction — a missed file
  fails the sweep rather than passing silently; + `widen_live_tree_guard_sweep`

### Planned mitigations
- timing: after | name: board_fixture_harness_docs | type: documentation | priority: low | effort: low | addresses: code-health — shared-harness blast radius / implicit contracts | desc: Add a `tests/lib/board_fixture.py` pointer and trap summary to `aidocs/framework/tui_conventions.md` (the discoverability question t1354_1 deferred to t1354_2)
- timing: after | name: widen_live_tree_guard_sweep | type: test | priority: low | effort: low | addresses: goal-achievement — guard completeness beyond board tests | desc: Widen the tier-1 live-tree sweep from `tests/test_board_*.py` to all `tests/test_*.py`, giving `DELIBERATELY_LIVE` its first provable entry (`test_shortcut_scopes.py:322`)

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no worktree to remove, output branch `main`
per this plan's header. Run the declared gates (`risk_evaluated`) via the
orchestrator (`./ait gates run 1354_2`), then archive with
`./.aitask-scripts/aitask_archive.sh 1354_2`.
