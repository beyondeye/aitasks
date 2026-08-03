---
Task: t1354_4_retrospective_measure.md
Parent Task: aitasks/t1354_speed_up_python_test_suite.md
Sibling Tasks: aitasks/t1354/t1354_1_board_fixture_harness.md, aitasks/t1354/t1354_2_migrate_remaining_board_tests.md, aitasks/t1354/t1354_3_parallel_test_lane.md
Archived Sibling Plans: aiplans/archived/p1354/p1354_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-03 12:13
---

# t1354_4 — Retrospective measurement + floor tuning

## Context

t1354 set out to cut `bash tests/run_all_python_tests.sh` from ~12 minutes.
Three siblings landed: t1354_1/t1354_2 moved 17 board TUI modules off the live
`aitasks/` tree onto `tests/lib/board_fixture.py`, and t1354_3 added the opt-in
`ait setup --with-dev` tier plus a bounded `-n 2 --dist loadfile` lane.

This child is the read-out: measure what actually landed against the parent's
projections, tune the identified floor **only** where data justifies it, file
evidence-backed follow-ups, and record the retrospective. The measurement record
is the deliverable — the parent archives when this child completes.

## Plan verification (2026-08-03)

Every claim in the task file and the prior plan draft was re-checked against
this checkout (HEAD `4f6c0b319`, data `fbcb90a3e`, working tree clean, dev tier
installed — pytest 8.4.2 + xdist, marker present, 179 test modules, 24 cores,
load average 1.76). **Five corrections, three of them load-bearing.**

### 1. The floor premise is superseded — the split is not the lever it was

Task step 2 and the prior plan say: *"identify the slowest single file; if it is
test_syncer_rows and it dominates, split it."* t1354_3 measured the end state
and that framing no longer describes this configuration:

| lane | measured (t1354_3, code `afa1eaa05`+13 files / data `eb2fda87d`) |
|---|---|
| unittest serial (no dev tier — what a user has today) | **419.8s**, 3124 tests |
| pytest serial (`AIT_TEST_PARALLEL=0`) | **431.1s** |
| pytest + xdist `-n 2 --dist loadfile` | **222.4s** |

Under `--dist loadfile` a file is pinned to one worker, so pool makespan is
roughly `max(F, W/N)` — `F` the slowest single file, `W` total work, `N`
workers. With `W≈431s` and `F≈124s` (test_syncer_rows), `W/2 = 215s` sits
**above** `F`, and the measured 222.4s confirms it. The binding constraint at
N=2 is total work ÷ workers, **not** the slowest file. Crossover is
`N* = W/F ≈ 3.5`; only past that does the split buy anything.

t1354_3's own hand-off says the same and names the cheaper experiment first:
raising `AIT_TEST_WORKERS`. So the decision this child owes the user is
**the default worker count**, from which the split decision falls out.

### 2. The suite is two sequential phases, not one pool — the model must say so

`tests/run_all_python_tests.sh:170-179` runs the parallel pool to completion and
**then** runs the serial carve-out (`test_board_header_row_live.py`) as a second
`pytest` invocation, combining exit statuses. The phases are strictly additive
and the carve-out is **invariant to `N`**:

```
M(N) ≈ max(F_pool, W_pool / N) + ε + T_carve
```

The prior draft modelled the suite as a single pool. That error grows with `N`:
as the pool shrinks, the fixed `T_carve` becomes a larger share of the total and
would be silently attributed to poor parallel scaling — distorting both the
worker-count decision and the split decision. Consequences for this plan:

- `T_carve` is measured **separately** (`python -m pytest
  tests/test_board_header_row_live.py -v`, which is exactly the runner's
  `serial_cmd` at `:153`), and reported as its own line in every table.
- `W_pool` and `F_pool` are computed over the **pool partition only** — the
  carved module is excluded from both, since it never competes for a worker.
- Scaling is reported against pool makespan (`M(N) − T_carve`), with total wall
  time reported alongside it as the user-facing number.

### 3. test_syncer_rows.py re-runs 75 tests for nothing (new finding)

The task, the parent plan and p1354_3 all record *"2797 lines, 18 classes, 136
tests, ~76 SyncerApp boots"*. Measured today:

```
python -m pytest tests/test_syncer_rows.py --collect-only -q  →  211 tests collected
```

`TabbedShellTests` (`:860`) defines **25 test methods of its own** *and* is the
helper base for three subclasses. Collected counts: `SettingsTabTests` 54,
`UpgradeActionTests` 41, `VersionsTabTests` 31, `TabbedShellTests` 25 — each
subclass inherits and re-runs the base's 25. So 211 collected, **151 booting a
real `SyncerApp`, of which 75 (~50%) are duplicate executions.**

**Redundancy proven by audit, not asserted** (AST audit run at plan time; see
Step 5, where it is re-run and recorded):

- The 25 base tests reference exactly four names on `self` beyond
  `unittest.TestCase` asserts: `_run`, `booted`, `settle`, `_focus_bar` — **all
  four defined by the base**.
- **No** subclass defines any of those four names (no shadowing), and none
  overrides `booted`/`settle`/`_run`/`_focus_bar`.
- Lifecycle hooks: the base defines **no** `setUp`/`setUpClass`.
  `UpgradeActionTests.setUp` (`:1528`) is the only one in the inheritance chain
  and creates a tmpdir exposed as `self._tmp`/`self.root` — names the base's 25
  tests never reference. `VersionsTabTests` and `SettingsTabTests` define no
  lifecycle hooks at all.
- No `getattr`/`setattr`/`hasattr`/`vars`/`eval` and no `global` statements in
  the 25 base tests, so the static audit is not defeated by dynamic access.

The structural fix is therefore coverage-neutral: a test-free `_TabbedShellBase`
holding the four helpers, a concrete `TabbedShellTests(_TabbedShellBase)`
holding the 25 tests, and the three subclasses re-pointed at the base.

This matters more than the split, and differently: de-duplication removes ~62s
of **total work `W_pool`**, so it helps at *every* worker count including
today's N=2 (predicted pool floor 215s → ~185s). The split only reduces
`F_pool`, which does nothing below the crossover. De-duplication also pushes the
crossover from `N≈3.5` to `N≈6`, likely making the split unnecessary at any
worker count the user would plausibly default to.

**USER DECISION (2026-08-03):** de-duplicate inside this task, then re-measure;
make the split decision against the de-duplicated floor.

Tree-wide AST scan of all 179 modules for the same pattern — a class subclassing
another class in the same module that defines its own `test_*` methods — found
**exactly one instance**, this one. No bulk cleanup is warranted; a structural
guard against recurrence is proposed as an "after" mitigation instead.

### 4. The baseline lineage is three different denominators, not one

The task's "746s baseline" is 2026-07-31, a smaller tree, unittest serial. The
chain is 746s → 643.5s (re-measured before t1354_2; the tree grew) → 400.4s
(t1354_2) → 419.8s (t1354_3 snapshot). Test counts moved too (2900 → 2969 →
2996 → 3124), so per-file ratios are the honest comparison and every suite
number is quoted with its backend, worker count and test count.

The parent's projections (fixtures → ~280s; +xdist → ~60–120s) were computed
against the *pre*-t1354_1 tree and assumed `-n auto`. Both will be missed. Per
the parent's own acceptance contract, a miss is presented to the user with the
data — never silently re-scoped.

### 5. Scope narrowed deliberately: one per-file sweep method, not two

Task step 1 says "re-run the per-file sweep … both backends". Two full sweeps
cost ~17 min for ~3% of signal. **Stated AC deviation:** one sweep is run with
`unittest discover -p <file>` — method-identical to the recorded 2026-07-31
baseline, so the before/after table is apples-to-apples — and per-file data *in
the lane's own backend* comes free from `--durations=0` on the pytest-serial run
that is happening anyway. The ~2.7% backend delta is far below the decision
margin and is recorded rather than hidden.

## Measurement surface

Every suite-level number comes from **pinned snapshot worktrees**, reusing
t1354_3 Step 7's proven recipe. This is not ceremony: the campaign runs over an
hour, concurrent sessions in this checkout have modified files mid-task before,
and the runner's `test_*.py` glob picks up untracked strays.

**Two code worktrees, one data worktree** — the second code tree is what makes
the decisive pre/post comparison interleavable rather than campaign-separated
(see Step 6):

```bash
data_sha="$(git -C .aitask-data rev-parse HEAD)"
git worktree add --detach ../t1354_4_verify_data "$data_sha"
git worktree add --detach ../t1354_4_pre  HEAD     # unsplit, un-deduped
git worktree add --detach ../t1354_4_post HEAD     # receives the dedup edit
for w in ../t1354_4_pre ../t1354_4_post; do
  (cd "$w" \
   && ln -s "$(cd ../t1354_4_verify_data && pwd)" .aitask-data \
   && ln -sfn .aitask-data/aitasks aitasks \
   && ln -sfn .aitask-data/aiplans aiplans)   # canonical relative form,
done                                          # per aitask_init_data.sh:55-56
```

Prove each tree before any number counts — `aitasks`/`aiplans` are gitignored
(`.gitignore:37-38`) so a fresh worktree has neither, and the board's
cwd-relative helpers degrade *silently*, so a broken snapshot yields a green run
over an empty tree:

```bash
readlink -e aitasks && readlink -e aiplans
[ -d aitasks/metadata ] || echo "SNAPSHOT NOT REPRESENTATIVE"
ls aitasks/t*.md >/dev/null
git status --porcelain          # only the symlink scaffolding + copied files
```

Record both SHAs with every run. **Never commit from a snapshot** — all commits
happen in the primary checkout. Scratch files (collection ID lists, timing logs)
are created with `mktemp` **inside the snapshot**, never at fixed `/tmp` paths:
the concurrent-session threat model this surface exists for applies to
`/tmp/before.ids` too, where another agent could overwrite the file and make a
`comm` diff report a misleading proof.

### Sampling discipline (what makes the numbers comparable)

Load average alone does not detect cache warming, I/O contention or short-lived
competing jobs, and a single pre-run separated from a single post-run by an
hour-long campaign would credit any of those to the structural change. So:

- **Warm-up.** One full discarded run at the start of the campaign (page cache
  for the repo, venv and git objects). `PYTHONDONTWRITEBYTECODE=1` is set by the
  runner, so bytecode caching is off in *every* run and cannot drift between
  them.
- **Interleave the decisive comparison.** The pre/post-dedup comparison at the
  default worker count is run **A/B/A/B/A/B** across the two pinned code trees —
  3 samples each, alternating — not as two campaign-separated samples. Report
  the **median and the full min–max spread**, and record every retained sample
  (t1354_2's precedent: both runs recorded, not the more flattering one).
- **Objective contamination rule.** Every run logs wall (`real`), `user+sys` CPU
  and load average at start and end. Discard and re-run a sample when either:
  (a) load average at start exceeds **3.0** on this 24-core box, or (b) wall
  time deviates **>10%** from its group median while `user+sys` stays within
  **3%** — the signature of external contention rather than a real change.
  Discarded samples are listed in the plan with their reason, never silently
  dropped.
- **Exploratory vs decisive.** The N=1,2,4,6,8 scaling curve is exploratory —
  one sample each is enough to establish *shape*. Any `N` that actually brackets
  a decision (the current default, and whichever the user is choosing between in
  Step 7) gets the 3-sample interleaved treatment before it is quoted.
- **`W_pool` is measured on both sides, never derived.** `W_pool` feeds the
  crossover `N* = W_pool / F_pool` and therefore the split rule, so it is
  measured pre- **and** post-dedup by the same instrument (a serial-pytest run
  with `--durations=0`, R1 and R1'), never by subtracting a per-file number
  taken with a different backend. Each is reported three ways — serial wall
  minus `T_carve`, the summed `--durations=0` per-test time, and `user+sys` CPU
  — and any material disagreement between them is stated rather than averaged
  away. One sample each is sufficient *because* `user+sys` CPU is nearly
  contention-independent and cross-checks the wall figure; **escalation rule:**
  if the resulting `N*` lands within ±0.5 of any `N` the user is deciding
  between in Step 7, R1/R1' are re-run under the full 3-sample interleaved
  discipline before the split rule is applied to them. Any figure that ends up
  derived rather than measured is labelled an estimate in the tables.

## Steps

### Step 1 — Build and prove the snapshots

As above. Record `code_sha`, `data_sha`, and the machine's concurrent load.
Run the warm-up and discard it.

### Step 2 — Pre-dedup measurement campaign

All runs `time bash tests/run_all_python_tests.sh` inside `../t1354_4_pre`, one
denominator, contamination fields logged per the sampling discipline:

| run | how | purpose |
|---|---|---|
| R0 | unittest serial | what a user without the dev tier has today |
| R1 | `AIT_TEST_PARALLEL=0` + `--durations=0` | pytest serial → `W`, plus free per-file data in the lane's backend |
| RC | `pytest tests/test_board_header_row_live.py -v` alone | `T_carve`, the additive second phase (correction 2) |
| R2–R6 | `AIT_TEST_WORKERS=1,2,4,6,8` | the scaling curve (USER DECISION: this range) |

R0 needs the unittest branch on a machine that *has* pytest. Use the documented
cwd shim (`tests/test_python_runner_exit_status.sh:20-30`): CPython puts cwd on
`sys.path` for both `-c` and `-m`, so a `pytest/__init__.py` that raises
`ImportError`, placed at the **snapshot root**, makes the runner's probe fail
while cwd stays the repo root (which the tests need). The runner resolves
`TEST_DIR`/`PROJECT_DIR` from `${BASH_SOURCE[0]}` (`:47-50`), so cwd does not
change which modules run. Remove the shim before the pytest runs and confirm the
banner reads `runner=pytest`.

Read **only** the last line for the verdict; use `set -o pipefail` /
`${PIPESTATUS[0]}` when piping (the banner is on stderr, the status is not).

### Step 3 — Per-file sweep and the two-phase model

`python -m unittest discover -s tests -p <file>` per module (179), timed —
method-identical to the 2026-07-31 baseline. From it derive **`W_pool` and
`F_pool` over the pool partition only**, excluding `test_board_header_row_live.py`
(carved, so it never competes for a worker).

Then state the model and check it against R2–R6:

```
M(N) ≈ max(F_pool, W_pool / N) + ε + T_carve
```

Report `ε` (worker startup + scheduling imbalance) as measured, quote scaling
against pool makespan `M(N) − T_carve`, and say plainly where the model fails if
it does.

### Step 4 — Analysis handoff

Produce the pre-dedup read-out: the before/after table vs the 2026-07-31
baseline, the scaling curve with `T_carve` broken out, the measured crossover,
and the projected-vs-achieved comparison against the parent's two projections.
No decisions yet — Steps 5–8 act on this.

### Step 5 — De-duplicate test_syncer_rows.py

Edit in the **primary checkout** (snapshots are for measuring, never for
committing):

- `tests/test_syncer_rows.py` — rename `TabbedShellTests` → `_TabbedShellBase`
  containing **only** the four helpers (`_run`, `booted`, `settle`,
  `_focus_bar`); add `class TabbedShellTests(_TabbedShellBase)` holding the 25
  test methods unchanged; re-point `VersionsTabTests`, `UpgradeActionTests`,
  `SettingsTabTests` at `_TabbedShellBase`. Pure moves — no test-logic edits.
  The leading `_` is what keeps the base out of collection, matching the
  `GitRepoTestBase` / `BrainstormCrewTestBase` precedent already in this tree.

**Three independent proofs, because none of them alone is sufficient:**

1. **Redundancy audit (re-run and recorded).** Re-run the plan-time AST audit
   and paste its output into the plan: the attribute set the 25 base tests touch
   on `self`; which of those the base provides; every name and lifecycle hook
   each subclass defines; the collision set (must be empty); and the absence of
   `getattr`/`setattr`/`hasattr`/`vars`/`eval` and `global`. **Scope stated:**
   this proves the inherited executions consume no subclass-specific state — it
   does not prove the re-runs were *intended* to be redundant, and that question
   is unchanged by this task (they never were reparametrized).
2. **Exact node-id set difference**, not a count comparison — neither existing
   guard covers a before/after collection *drop* (`test_no_zero_collection.py`
   asserts only ≥1; `test_collection_parity.py` compares *backends*). Scratch
   files via `mktemp` inside the snapshot, cleaned after:
   ```bash
   ids=$(mktemp -d "$PWD/.t1354_4_ids.XXXXXX")
   python -m pytest tests/test_syncer_rows.py --collect-only -q | sort > "$ids/before"
   # … after the edit …
   comm -23 "$ids/before" "$ids/after"   # MUST be exactly the 75 duplicates:
                                         # {Settings,Upgrade,Versions}Tab* × the 25 base method names
   comm -13 "$ids/before" "$ids/after"   # MUST be empty — nothing new, nothing renamed away
   rm -rf "$ids"
   ```
3. **Behavioral proof.** Before the edit, run the 75 duplicate node-ids
   explicitly and confirm all 75 pass — that is their entire contribution, so
   removing passing executions that consume no subclass state removes no signal.
   After the edit, `tests/test_syncer_rows.py` is green under **both** backends
   with 136 collected.

`test_no_zero_collection.py` and `test_collection_parity.py` must stay green
with empty allowlists.

### Step 6 — Post-dedup re-measure (interleaved)

Copy **only** the changed file into `../t1354_4_post`, re-confirm
`git status --porcelain` lists only this task's files, then:

- **Decisive:** A/B/A/B/A/B at the current default N=2 across `../t1354_4_pre`
  and `../t1354_4_post` — 3 samples each, median + spread, per the sampling
  discipline. This is the number the de-dup claim rests on.
- **R1' — the post-dedup work measurement.** `AIT_TEST_PARALLEL=0` +
  `--durations=0` in `../t1354_4_post`, the exact counterpart of R1. This is
  what yields the new `W_pool` and the new `F_pool` **in the pool's own backend**
  — neither is derived by subtracting the unittest sweep's per-file number, which
  would mix backends into a pytest-pool quantity that the crossover and the split
  rule both depend on. Report it three ways (serial wall minus `T_carve`, summed
  `--durations=0`, `user+sys` CPU) and apply the escalation rule from the
  sampling discipline if `N*` lands near a candidate `N`.
- **Curve:** `../t1354_4_post` at N=2,4,6,8 (one sample each for shape).
- `T_carve` re-measured once to confirm it is unchanged (it must be — the
  carved module is untouched).

The unittest per-file sweep (Step 3) is **not** re-run post-dedup: its role is
comparability with the 2026-07-31 baseline, which only the pre-dedup side needs.
Post-dedup per-file data comes from R1's and R1''s `--durations=0`, so the
before/after per-file comparison for `test_syncer_rows.py` is backend-consistent
on both sides.

Predicted: file ~124s → ~62s, `W_pool` −62s, N=2 total ~222s → ~190s, crossover
`N*` ≈ 6. **Predictions are written down before measuring so they can be
falsified** — report measured against them either way.

### Step 7 — Present the data; the user decides the default worker count

This runs **before** the split decision, because the split rule is defined
against the chosen `N` and cannot be evaluated until that choice exists.

One `AskUserQuestion` carrying the measured tables, covering:

1. **The two missed projections** (fixtures ~280s; +xdist ~60–120s) — accept as
   the settled read-out, or open further work.
2. **The default worker count** — keep 2 (the standing USER DECISION, made
   because ~10 agents commonly run here), or raise it given the measured curve,
   the `T_carve` floor it cannot go below, and the contention cost.

Never auto-revise the task or the parent's contract. If the default changes, the
same commit must update `tests/run_all_python_tests.sh:135`, the exact-argv
assertions in `tests/test_python_runner_exit_status.sh` that pin `-n 2`, and the
`CLAUDE.md` Testing table — otherwise the contract test fails by design.

### Step 8 — Split decision, against the *chosen* worker count

Now that `N_default` is decided, apply the rule and record the reasoning either
way:

- Split **only if** the de-duplicated `F_pool` binds at `N_default` (i.e.
  `W_pool / N_default < F_pool`) **and** the projected saving on total wall time
  — including the additive `T_carve`, which the split cannot reduce — is ≥20%.
- **If it splits:** partition by measured **per-class wall time** (not class
  count) into 2–3 files, promoting `Seams` (`:746`) and `_TabbedShellBase` to
  one importable module so nothing is forked. Then:
  - re-run the Step 5 node-id set check tree-wide — a split moves node-ids
    *between* files while the tree-wide set stays identical;
  - **re-measure at `N_default`** with the same 3-sample interleaved discipline
    (`../t1354_4_post` vs a third tree carrying the split), so the final
    read-out describes the state that actually ships.
- **If it does not** (the expected outcome at N=2): do not split, and record the
  crossover `N` at which it would start to pay.

### Step 9 — Flake probe

Diff the failure sets across the repeat runs already produced by Steps 6/8 at
`N_default` (they double as the flake samples), plus two runs at N=8 — the worst
contention. Any test that fails only under contention becomes a standalone
follow-up with the evidence inline. t1354_3 explicitly deferred repeat-run flake
hunting to this child.

### Step 10 — Follow-ups and the retrospective

File standalone tasks **only** where the data justifies them. Then write the
retrospective into this plan's Final Implementation Notes: projected vs achieved
(with backend, worker count, test count and both SHAs beside every number), the
decisions taken and why, discarded samples and their reasons, and the follow-ups
filed. Explain the tree-wide test count dropping by 75 (3124 → ~3049) as
*removed duplicate executions, not lost coverage* — otherwise a future reader
will misread it as a regression.

### Step 11 — Cleanup

Only **after** the evidence is written into the plan (the code worktrees are
deliberately dirty, so a plain remove refuses):

```bash
git worktree remove --force ../t1354_4_pre
git worktree remove --force ../t1354_4_post
git worktree remove --force ../t1354_4_verify_data
git worktree prune
```

## Verification

- Every snapshot proven before any number counts (`readlink -e` on both entry
  points, non-empty task tree, `git status --porcelain` showing only this task's
  files); scratch files created via `mktemp` inside the snapshot and removed.
- Suite green in **every** recorded run; verdict read from the last line only.
- Every table breaks out `T_carve` separately from pool makespan, and `W_pool` /
  `F_pool` exclude the carved module.
- Decisive comparisons are 3-sample interleaved with median + spread; every
  discarded sample is listed with the contamination rule that rejected it.
- `W_pool` and `F_pool` are **measured** on both sides of the de-dup by the same
  instrument (R1 / R1', serial pytest + `--durations=0`), each reported three
  ways with any disagreement stated; nothing feeding the crossover or the split
  rule is derived by cross-backend subtraction, and any derived figure that
  remains is labelled an estimate.
- De-dup: all three proofs recorded — the audit output, the exact node-id set
  difference (exactly the 75 duplicates removed, nothing added), and the 75
  passing before removal. `test_no_zero_collection.py` and
  `test_collection_parity.py` green with empty allowlists;
  `tests/test_syncer_rows.py` green under both backends at 136 collected.
- If split: tree-wide node-id set unchanged, all files green under both
  backends, and the final read-out re-measured at `N_default` post-split.
- **No target is asserted** — results are reported as measured, decomposed so
  the backend switch (~2.7% slower) is never attributed to parallelism.
- The plan contains the complete before/after tables and an explicit disposition
  for every parent projection.

**Time budget, stated honestly:** ~77–92 minutes of sequential test execution
(~4 min warm-up, ~31 min pre-dedup campaign, ~8 min sweep, ~20 min interleaved
decisive runs, ~6 min R1', ~7 min post-dedup curve, ~5 min flake probe), plus
two contingencies: a re-measure if the split happens, and ~25 min more if the
`N*` escalation rule fires and R1/R1' need the full 3-sample treatment. The
machine is idle now (load 1.76); N=6/8 runs take 6–8 of 24 cores.

## Risk

### Code-health risk: medium
- The de-dup deletes 75 test executions; a mistake in which class holds which
  method would silently drop **real** coverage, and no existing guard catches a
  before/after collection *drop* · severity: medium · → mitigation: three
  independent proofs in Step 5 (state-consumption audit, exact node-id set
  difference with the removed set enumerated in advance, and the 75 shown
  passing beforehand); pure moves, no test-logic edits
- `tests/test_syncer_rows.py` is 2797 lines and a split would move whole classes
  across files, where a shared-helper import can fork or a class can be dropped
  · severity: medium · → mitigation: the split is conditional on Step 8's rule,
  partitions by measured per-class time, promotes `Seams`/`_TabbedShellBase` to
  one importable module, and re-runs the node-id set check tree-wide
- Raising the default worker count would touch `tests/run_all_python_tests.sh`,
  which is on every task's verification path · severity: medium · → mitigation:
  only on explicit user decision (Step 7), and the exact-argv contract
  assertions pinning `-n 2` fail by design until updated in the same commit
- The duplicate-inheritance pattern can silently return the next time someone
  subclasses a test-defining class · severity: low · → mitigation:
  `syncer_inherited_test_dup_guard` (**t1384**, "after")
- Running the suite in the live checkout would collide with concurrent sessions
  over the real git index · severity: low · → mitigation: pinned snapshot
  worktrees; the one module touching the real index is already carved serial

### Goal-achievement risk: medium
- A >1-hour campaign on a shared machine can be contaminated by cache warming,
  I/O contention or short-lived competing jobs, and a campaign-separated pre/post
  pair would credit any of those to the structural change · severity: **medium**
  · → mitigation: warm-up run discarded, decisive comparisons interleaved
  A/B/A/B/A/B across two pinned trees with 3 samples each, and an objective
  contamination rule (load >3.0, or wall deviating >10% from group median while
  `user+sys` holds within 3%) that forces a re-run and records the discard
- Modelling the suite as one pool would misattribute the additive, N-invariant
  serial carve-out to poor parallel scaling, distorting both the worker-count
  and split decisions · severity: medium · → mitigation: `T_carve` measured
  separately and broken out of every table; `W_pool`/`F_pool` computed over the
  pool partition only (correction 2)
- The predicted post-dedup numbers (~62s file, `N*`≈6) may not materialize if
  boot cost is not proportional to boot count · severity: low · → mitigation:
  predictions written down *before* measuring so they can be falsified, and the
  measured result reported either way
- The retrospective could quietly absorb the two missed projections instead of
  surfacing them · severity: low · → mitigation: Step 7 is an explicit
  user-facing disposition prompt, per the parent's acceptance contract
- The split may not deliver a proportional floor drop if the remaining classes
  are unevenly sized · severity: low · → mitigation: partition by measured
  per-class wall time, not by class count

### Planned mitigations
- timing: after | name: syncer_inherited_test_dup_guard | created: t1384 | type: test | priority: low | effort: low | addresses: code-health — the duplicate-inheritance pattern can silently return | desc: Structural guard asserting no `tests/test_*.py` class subclasses another class in the same module that defines its own `test_*` methods (the base's tests are then re-executed once per subclass — 75 wasted boots in test_syncer_rows.py before t1354_4). Reuse the AST scan written during t1354_4 planning, which found exactly one tree-wide instance; ship with a negative control proving the guard flags a synthetic offender.

## Measured results

Machine: 24 cores. Pinned **code `6c487b8be`** / **data `a47b40bc7`**, in the
`../t1354_4_pre` and `../t1354_4_post` snapshot worktrees. Ambient load across
the campaign 0.84–3.94 (the box quietened to ~1 partway through, after a
concurrent agent's benchmark finished). Every suite run below **PASSED**.

The snapshot earned its keep immediately: the primary checkout carried another
session's uncommitted work, including an **untracked `tests/test_board_render_scoping.py`**
that the runner's `test_*.py` glob would have swept into every measurement.

### Suite wall clock — one denominator

| lane | pre-dedup | post-dedup | tests |
|---|---|---|---|
| unittest serial (**no dev tier — what a user has by default**) | **408.4s** | — | 3136 |
| pytest serial (`AIT_TEST_PARALLEL=0`) | 424.4s | 380.6s | 3135 → 3060 |
| xdist `-n 1` | 423.7s | — | 3135 |
| xdist `-n 2` (the old default; median of 3 interleaved) | **221.3s** | **200.1s** | 3135 → 3060 |
| xdist `-n 4` | 143.3s | **111.3s** / 115.6s | 3135 → 3060 |
| xdist `-n 6` | 145.1s | 101.0s | 3060 |
| xdist `-n 8` | 145.5s | 101.4s | 3060 |
| **shipping state** (load-aware default → `-n 4`, quiet box) | — | **115.6s** | 3060 |

**Headline: 408.4s → 115.6s = 3.53x** against what a user without the dev tier
has today.

Two `-n 4` post-dedup samples are recorded (111.3s and 115.6s, 3.9% apart)
rather than the more flattering one. That spread is the honest run-to-run
variance of the single-sample curve points; it changes no decision here, because
every effect the decisions rest on is a 40%+ effect.

### The structural result — where the time actually goes

Derived from `--durations=0` on the serial-pytest runs, i.e. measured in the
lane's own backend on both sides, never by cross-backend subtraction:

| quantity | pre-dedup | post-dedup |
|---|---|---|
| `W_pool` (total work, 110–111 pool modules) | 410.9s | 366.4s |
| `F_pool` (slowest single file — `test_syncer_rows.py` both times) | 133.1s | 87.1s |
| crossover `N* = W_pool / F_pool` | **3.09** | **4.21** |
| `T_carve` (serial carve-out phase, N-invariant) | 3.71s | 3.71s |

**`M(N) ≈ max(F_pool, W_pool/N) + ε + T_carve` holds.** Residual ε = +6.5 to
+9.1s pre-dedup, +10.1 to +16.0s post-dedup (worker startup + scheduling
imbalance). Modelling the suite as a single pool would have been wrong — the
carve-out is a genuinely additive second phase — but at 3.71s it is a small
constant, not the distortion the plan budgeted for. The 45s figure in the
runner's comment is a *boot budget*, not a cost.

The plateau is the whole story: **pre-dedup the suite cannot go below ~143s at
any worker count**, because one file is 133.1s of it. Post-dedup the wall moves
to ~101s.

### Per-file sweep (unittest per module, method-identical to the 2026-07-31 baseline)

180 modules, sum **424.4s**, every module exit 0.

| file | 2026-07-31 | today | note |
|---|---|---|---|
| `test_syncer_rows.py` | 124s | **125.2s** (211 tests) | untouched by t1354_1–3, as expected |
| `test_board_bytrail_view.py` | 165s | **40.2s** | t1354_1 fixture migration (tree has grown since) |
| `test_board_movement.py` | — | 27.8s | |
| `test_board_scroll_focus_jump.py` | — | 21.2s | the one 1.1x migration in t1354_2 |

### The de-duplication — decisive interleaved comparison

`A/B/A/B/A/B` at N=2 across the two pinned trees, 3 samples each:

- pre-dedup: median **221.3s** (221.1 / 221.3 / 221.5 — spread 0.4s)
- post-dedup: median **200.1s** (198.0 / 200.1 / 204.8 — spread 6.8s)
- **effect: −21.2s (9.6%), 1.106x**
- CPU cross-check (contention-insensitive): 240.6s → 227.9s, −12.7s
- Contamination rule (wall >10% off group median while CPU within 3%):
  **no samples flagged**

Test count 3135 → 3060 = **−75 exactly**. That is removed *duplicate
executions*, **not lost coverage** — see the three proofs below.

### Predictions written before measuring — three falsified

Recorded so they could be falsified, and they were:

| prediction | measured | verdict |
|---|---|---|
| `test_syncer_rows.py` ~62s post-dedup | **87.1s** | **falsified** — the file carries ~20s of non-boot fixed cost, so time is not proportional to boot count |
| `W_pool` −62s | **−44.5s** | **falsified**, same cause |
| crossover `N*` ≈ 6 | **4.21** | **falsified** — `F_pool` was 133.1s, not the 124s assumed |
| N=2 total ~190s | 200.1s | slightly optimistic |

### Flake probe

**18 full-suite runs** across the campaign (including N=8, the worst
contention) plus 3 carve-out runs: **zero failures, zero flakes.** No
contention-only failure appeared, so no flake follow-up is warranted —
discharging the repeat-run flake hunting t1354_3 deferred to this child.

## Dispositions

### Parent projections — accepted as the settled read-out (USER DECISION 2026-08-03)

- **Fixtures → ~280s: MISSED.** Measured 408.4s unittest serial. The projection
  was computed against the smaller pre-t1354_1 tree; the suite grew from ~2900
  to 3136 tests in the meantime, so the target moved underneath it.
- **+xdist → 60–120s: MET by the shipping configuration.** Missed at the old
  `-n 2` default (221.3s), but the load-aware default lands at **115.6s** on a
  machine with headroom — inside the band — and `-n 6` reaches 101.0s.

t1354 closes on these numbers; no further in-family work opened.

### Worker count — made dynamic (USER DECISION 2026-08-03)

Rather than choosing one constant, the default is now **load-aware: 4 when the
box has headroom (≥4 cpus and 1-min load ≤ cpus/2), 2 otherwise.** This resolves
the tension the original cap existed for — N=4 is 1.80x faster than N=2 for ~10%
more CPU, but taking 4 cores unconditionally would starve the ~10 agents that
commonly run here.

The load-dependence is confined behind `AIT_TEST_LOADAVG` / `AIT_TEST_NCPU`
**test seams**, because a load-dependent argv would otherwise make
`test_python_runner_exit_status.sh` machine- and moment-dependent — precisely
the defect class t1354_3's blocking xdist shim was added to remove.

### Split of `test_syncer_rows.py` — NOT DONE, and the arithmetic says why

The rule was: split only if `F_pool` binds at the chosen default **and** the
saving is ≥20%. At the shipping default `N=4`:

```
W_pool / 4 = 91.6s   >   F_pool = 87.1s      → the floor is NOT binding
```

Total work ÷ workers still dominates, so splitting the file would buy **≈0** at
N=4. It only begins to pay at **N ≥ 6**, where `W_pool/6 = 61.1s < 87.1s` and
the file becomes the sole constraint — there, splitting into ~3 whole-class
pieces would drop the floor toward `test_board_bytrail_view.py` (38.7s) and take
N=6 from 101.0s to roughly 75s. Recorded for whoever raises the default past 4;
the de-duplication already moved the crossover from 3.09 to 4.21.

## Final Implementation Notes

- **Actual work done:** the measurement campaign (18 full-suite runs + a
  180-module per-file sweep, all in pinned snapshot worktrees), plus three code
  changes the data justified:
  1. `tests/test_syncer_rows.py` — `TabbedShellTests` split into a test-free
     `_TabbedShellBase` (the four boot helpers) and a concrete
     `TabbedShellTests` holding its 25 tests; `VersionsTabTests`,
     `UpgradeActionTests` and `SettingsTabTests` re-pointed at the base. Pure
     moves, no test-logic edits. 211 → 136 collected.
  2. `tests/run_all_python_tests.sh` — the fixed `-n 2` default replaced by a
     load-aware `default_workers()` (4 with headroom, 2 under load), behind
     `AIT_TEST_LOADAVG` / `AIT_TEST_NCPU` test seams. A malformed
     `AIT_TEST_WORKERS` now falls back to that same default rather than a second
     hard-coded constant, so "the default" has one meaning. The auto-selected
     count is announced on stderr.
  3. `tests/test_python_runner_exit_status.sh` — the default-path assertion was
     machine-dependent the moment the default became load-aware, so it now
     drives **both** branches through the seams, plus a small-box case (an
     idle 2-cpu machine must still get 2) and a stronger override test. 56 → 61
     assertions.
  4. `CLAUDE.md` — knob table updated with the measured basis.

- **Deviations from plan:** four, all recorded above in place.
  1. **The split was not done** — the plan allowed for it, the measured
     arithmetic ruled it out at the chosen default (`W_pool/4 = 91.6s >
     F_pool = 87.1s`). See "Dispositions".
  2. **The worker count became dynamic rather than a constant** (USER
     DECISION). This was not in the plan, which offered only "keep 2 / raise
     to N". It required the test-seam design to keep the runner's argv
     contract deterministic.
  3. **The contamination gate was recalibrated from load<3.0 to load<6.0**
     (USER DECISION) after the box's ambient load turned out to be ~4.5, making
     the planned threshold unsatisfiable. It became moot: a concurrent agent's
     benchmark finished and the box quietened to ~1 for most of the campaign.
  4. **One per-file sweep, not two backends** — stated AC deviation, recorded
     in the plan's correction 5.

- **Issues encountered:**
  - **A concurrent session made the primary checkout unusable as a measurement
    surface**, exactly as the plan anticipated: untracked `tests/test_board_render_scoping.py`
    (reachable by the runner's glob) plus modified `aitask_board.py` and
    `aitask_setup.sh`. The pinned snapshots isolated all of it. Main also
    advanced twice mid-task (`4f6c0b319` → `6c487b8be` → `2b754b59d`); the
    measurements stay attributable because both halves were pinned by SHA.
  - **I had to abort the first campaign.** Another agent was recording a
    timing-sensitive board benchmark on the same box; my suite run was
    contaminating it and vice versa. Killed mine (the warm-up is discarded
    anyway) and restarted after theirs finished. The orphaned pytest pool
    survived `pkill` on the script name and needed a process-group kill.
  - **`setsid` broke background-completion tracking** — it forks and returns
    immediately, so the harness reported the campaign "complete" seconds after
    launch while it ran on detached. Needed an explicit
    wait-for-sentinel poller.
  - **`/usr/bin/time` is not installed here**; the harness uses bash's `time`
    keyword with `TIMEFORMAT` instead.

- **Key decisions:**
  - **De-duplicate rather than split.** The 75 duplicate executions were ~50%
    of the file's boots and cost ~46s; removing them reduces *total work*, which
    helps at every worker count, whereas splitting only lowers the floor and
    does nothing below the crossover.
  - **Load-dependence confined behind test seams.** Injecting both load and cpu
    count keeps `test_python_runner_exit_status.sh` deterministic on any
    machine — including small boxes, where a real `os.cpu_count()` under 4 would
    otherwise silently turn the quiet-box case into the loaded-box case.
  - **Predictions written down before measuring.** Three were falsified and are
    reported as such rather than quietly dropped.
  - **Both `-n 4` samples reported** (111.3s / 115.6s), not the flattering one.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:** t1354_4 is the last child; t1354 archives with
  it. For anyone revisiting suite performance:
  - **The suite's floor is one file.** `test_syncer_rows.py` is 87.1s of 366.4s
    total work post-dedup. Past `N=4` it is the sole constraint, and no worker
    count fixes that — only splitting it (into ~3 whole-class pieces, dropping
    the floor toward `test_board_bytrail_view.py` at 38.7s) would.
  - **Adding a test class that subclasses another test-defining class silently
    re-runs the base's tests once per subclass.** That cost 75 boots here. The
    `syncer_inherited_test_dup_guard` follow-up makes it non-recurring.
  - **Measure in a pinned snapshot worktree**, not the working checkout — the
    recipe is in "Measurement surface" above, and it caught real pollution
    twice in this task alone.

## Step 9 (Post-Implementation)

Current-branch mode (profile `fast`): no worktree to remove — the three
verification worktrees are cleaned in Step 11 above. Output branch `main` per
this plan's header. Run the declared gates (`./ait gates run 1354_4`), then
archive with `./.aitask-scripts/aitask_archive.sh 1354_4`. This is the last
child of t1354, so the parent archives with it.
