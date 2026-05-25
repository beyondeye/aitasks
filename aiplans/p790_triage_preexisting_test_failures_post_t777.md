---
Task: t790_triage_preexisting_test_failures_post_t777.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: Triage pre-existing test failures (post-t777 baseline)

## Context

t734 (test-scaffold helper port) captured an 11-test baseline of pre-existing
failures on `main` (commit `a124727a`, 2026-05-18). t790's job is to re-run
the whole-suite driver after t777 (modular pick skill, 27 archived children,
3 still pending) lands and triage what's left — file individual follow-up
tasks per root cause, or document dismissals.

This task is the **triage**, not the fix. Output is N follow-up tasks (and a
record of any dismissals in this plan's Final Implementation Notes).

## Re-baseline (captured 2026-05-25 on `main`)

Whole-suite driver (from `aiplans/archived/p734_*.md` §Step 3) reports:

```
PASS: 130  FAIL: 10
  tests/test_codeagent.sh
  tests/test_kill_agent_pane_smart.sh
  tests/test_multi_session_monitor.sh
  tests/test_multi_session_primitives.sh
  tests/test_opencode_setup.sh
  tests/test_tmux_control_resilience.sh
  tests/test_tmux_control.sh
  tests/test_tmux_exact_session_targeting.sh
  tests/test_tmux_run_parity.sh
  tests/test_tui_switcher_multi_session.sh
```

**Delta vs the 2026-05-18 baseline:** 1 test fixed (`test_skill_verify.sh` —
presumably resolved by t777_23 `task-workflown` → `task-workflow` swap).
Same 10 remain. PASS count rose 110 → 130, consistent with t777_27's parity
test additions landing in the meantime.

## Triage results — three root-cause buckets

### Bucket A — Test scaffold missing a sourced lib (1 test)

**`test_codeagent.sh`**

Reproduced with `bash -x`. `aitask_codeagent.sh:18` sources
`lib/agent_string.sh`, but `setup_fake_aitask_repo()` in
`tests/lib/test_scaffold.sh` does not copy `agent_string.sh` into the fake
repo's `.aitask-scripts/lib/`. The test fails at "Test 2: list-agents" with:

```
.aitask-scripts/aitask_codeagent.sh: line 18:
.../lib/agent_string.sh: No such file or directory
```

**Classification:** test fixture defect. Either (a) add a per-test
`cp .aitask-scripts/lib/agent_string.sh ...` in `test_codeagent.sh` itself
(domain-lib usage, not a system-lib chain expansion), or (b) elevate
`agent_string.sh` into the scaffold helper if multiple tests need it. The
CLAUDE.md note ("Current baseline: `aitask_path.sh`, `terminal_compat.sh`,
`python_resolve.sh`") implies the helper is for `./ait` source-chain libs
only — `agent_string.sh` is sourced by `aitask_codeagent.sh` (a domain
helper), so option (a) is preferred per the "helper is the floor, not a
ceiling" guidance in p734.

**Follow-up:** 1 `bug` task — _Fix `test_codeagent.sh` scaffold: copy
`agent_string.sh` to fake repo before exercising `aitask_codeagent.sh`._

### Bucket B — Glob mismatch after t777 added profile-variant skills (1 test)

**`test_opencode_setup.sh`**

Tests 1 and 2 both fail with `expected: '50', got: '44'`. Root cause is a
glob-vs-count divergence in the test itself:

- `expected_skill_count = find .opencode/skills -mindepth 2 -maxdepth 2
  -name SKILL.md` → counts **all** `<dir>/SKILL.md`, returns 50.
- The copy loop uses `for skill_dir in "$REPO_DIR/.opencode/skills"/aitask-*/`
  → only matches the `aitask-*` prefix, copies 44.

The 6 non-matching dirs were added by t777's profile-aware skill conversion:
```
.opencode/skills/task-workflow-fast-/SKILL.md
.opencode/skills/task-workflow-default-/SKILL.md
.opencode/skills/task-workflow-remote-/SKILL.md
.opencode/skills/user-file-select-default-/SKILL.md
.opencode/skills/user-file-select-fast-/SKILL.md
.opencode/skills/user-file-select-remote-/SKILL.md
```

These are legitimately not `aitask-*`-prefixed (they're shared closures, not
top-level user-facing skills). The fix is in the **test**, not the skill
catalog: broaden the copy glob and the staging loop to include
`task-workflow-*-/` and `user-file-select-*-/` (or, more general, switch
both expected count and copy loop to use the same glob).

**Follow-up:** 1 `test` task — _Fix `test_opencode_setup.sh` glob mismatch:
copy loop misses profile-variant `task-workflow-*-` /
`user-file-select-*-` skills that the expected count includes._

### Bucket C — tmux-guard early-exit counted as failure (8 tests)

All 8 tmux / multi-session / TUI-switcher tests emit:

```
ERROR: test_*.sh cannot run from inside a tmux session.
This test creates and tears down its own tmux server. Past failures have
cascaded into the surrounding user server, killing every pane inside it ...
```

and exit non-zero. This is the **intended safety guard** (added after a real
incident where a failing tmux test killed the user's surrounding server) —
not a code or fixture defect. The 8 tests:

- `test_tmux_control.sh`
- `test_tmux_control_resilience.sh`
- `test_tmux_exact_session_targeting.sh`
- `test_tmux_run_parity.sh`
- `test_kill_agent_pane_smart.sh`
- `test_multi_session_monitor.sh`
- `test_multi_session_primitives.sh`
- `test_tui_switcher_multi_session.sh`

The whole-suite driver (`p734_*.md` §3) treats any non-zero exit as failure,
so the guard pollutes the failure set whenever the suite is run from inside
tmux (which is essentially always for the maintainer).

This is one root cause across all 8. Options for the fix task:

1. Have each guarded test exit with a distinct **skip** code (e.g., 77 — the
   GNU autotools convention) and have the regression driver bucket exit-77
   as SKIP, not FAIL.
2. Pull the guard into a shared helper (`tests/lib/test_scaffold.sh`?) that
   emits the SKIP signal centrally so the driver can detect it.
3. Document the guard in the regression-loop snippet and tell users "run
   tmux tests from a fresh, non-tmux terminal; expect 8 SKIPs inside tmux."

The fix task should choose between 1+2 (mechanical, one-shot) and 3
(documentation-only); option 1+2 is preferred so the headline failure count
is accurate by default.

**Follow-up:** 1 `test` task — _Distinguish tmux-guard SKIPs from real test
failures in the regression driver (8 tests affected)._

## Follow-up tasks to create (via Batch Task Creation Procedure)

1. **bug** — `fix_test_codeagent_scaffold_missing_agent_string` — Add
   `agent_string.sh` copy to `test_codeagent.sh`'s setup so the sourced
   dependency resolves inside the fake repo. References this task (t790) in
   description.
2. **test** — `fix_test_opencode_setup_glob_mismatch` — Broaden the copy/
   staging loops in `test_opencode_setup.sh` to include profile-variant
   skills (`task-workflow-*-`, `user-file-select-*-`) so the actual count
   matches the expected count. References this task and t777 in description.
3. **test** — `tmux_guarded_tests_skip_exit_code` — Use a distinct skip exit
   code (e.g., 77) in the 8 tmux-guard early-exit branches and teach the
   regression-loop snippet to bucket those as SKIP. References this task
   and lists the 8 affected tests.

Each follow-up task gets `depends: [790]` and a short `## Context` block
pointing back here. Created with `aitask_create.sh --batch` per
`.claude/skills/task-workflow-fast-/task-creation-batch.md`.

## Dismissals

None. Each remaining failure has a clear, contained fix worth filing.

## Critical files (this task)

This task creates task files only — no source-code changes:

- `aitasks/t<id1>_fix_test_codeagent_scaffold_missing_agent_string.md` (new)
- `aitasks/t<id2>_fix_test_opencode_setup_glob_mismatch.md` (new)
- `aitasks/t<id3>_tmux_guarded_tests_skip_exit_code.md` (new)

Plan file consolidation (Step 8) updates this file with the assigned task
IDs once `aitask_create.sh --batch` returns them.

## Verification

- Re-baseline command output captured in this plan (130 PASS / 10 FAIL).
- Three new task files exist in `aitasks/` with `depends: [790]`, each
  referencing the relevant test name(s) and root cause from the buckets
  above.
- Final Implementation Notes records the assigned task IDs and any deviation
  from the buckets above (e.g., if user opts to merge two buckets into one
  task, that gets logged here).
- No code changes in this task — `git diff --stat` for non-task/non-plan
  paths is empty.

## Step 9 — Post-Implementation

Standard archival flow per task-workflow Step 9. Profile `fast`, current
branch — no worktree to remove.

## Final Implementation Notes

- **Actual work done:** Captured the post-t777 baseline (130 PASS / 10 FAIL
  — 1 down from the 2026-05-18 baseline of 11 FAIL, the dropped test being
  `test_skill_verify.sh`). Reproduced each remaining failure (logs in
  `/tmp/t790_logs/`), classified into three root-cause buckets, and filed
  three follow-up tasks:
  - **t827** (bug, depends: [790]) — `tests/test_codeagent.sh` scaffold is
    missing a copy of `lib/agent_string.sh` (sourced by
    `aitask_codeagent.sh:18`).
  - **t828** (test, depends: [790]) — `tests/test_opencode_setup.sh`
    `expected_skill_count` count-glob differs from the packaging/staging
    copy-glob; the 6 t777 profile-variant skills (`task-workflow-*-`,
    `user-file-select-*-`) are counted but not copied.
  - **t829** (test, depends: [790]) — the regression-loop driver buckets
    the tmux-safety-guard early exits (8 tests) as FAIL; switch to a SKIP
    exit code (e.g. 77) and teach the driver to surface SKIP separately.
- **Deviations from plan:** None. The bucketing matched the plan exactly;
  no dismissals.
- **Issues encountered:** `aitask_create.sh --batch` accepts `--deps`
  (line 75 of the script), but I omitted it on the initial creates and
  patched it after the fact with three `aitask_update.sh --batch
  --deps "790"` calls + one follow-up commit. Minor process nit — next
  time, pass `--deps 790` to the original create call.
- **Key decisions:**
  - All 10 failing tests fit cleanly into 3 root causes, so 3 follow-up
    tasks rather than 10.
  - Bucket-C fix (tmux SKIP exit code) routed to a single task even though
    it touches 8 test files — they share one root cause (the guard +
    driver contract), so one task is correct per
    `aidocs/planning_conventions.md` (lists-touching-3-plus-files rule).
  - For t827, recommended scoping the `agent_string.sh` copy to
    `tests/test_codeagent.sh` rather than
    `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` because
    `agent_string.sh` is a domain lib, not a `./ait` source-on-startup
    system lib. CLAUDE.md is explicit about the scaffold's "Current
    baseline" being system libs only (`aitask_path.sh`,
    `terminal_compat.sh`, `python_resolve.sh`).
- **Upstream defects identified:** None. All three follow-up tasks are
  defects in the **tests themselves** (or the regression-driver contract),
  not in production code. The `aitask_codeagent.sh` /
  `lib/agent_string.sh` / `.opencode/skills/*-*-/` paths under test are
  all behaving correctly — the test fixtures simply drifted.
