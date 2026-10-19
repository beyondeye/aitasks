---
Task: t2055_fix_test_fixture_cleanup_lost_in_subshell_sweep.md
Base branch: main
Output branch: main
---

# t2055 — Fix test fixtures leaked through `$( )` cleanup registration

## Context

t2031 found that `make_fixture` in `tests/test_docs_vocabulary_coverage.sh` appended
to `CLEANUP_DIRS` inside a `$(make_fixture)` command substitution. The append dies
with the subshell, so cleanup never sees the dir and the suite leaks while reporting
green. t2031's sweep listed 20 more suites with the same shape.

**What I confirmed** (probe: `TMPDIR=<empty dir> bash tests/<suite>.sh`, then count
what is left):

- **19 of the 20 listed suites leak.** Every helper is the same shape:
  `mktemp -d` → `CLEANUP_DIRS+=` → echo the path, called as `X="$(helper …)"`.
  Leaked fixture dirs per run:
  - gate_verifiers 60, gates_sync_registry 28, verification_stale 18,
    gate_orchestrator 18, skill_errexit_capture 24, run_project_command (many),
    active_gates 14, atomic_task_file_writes 8+7, amend_guard 10,
    procedure_docs 10, risk_verifier 10
  - pass 6, web_merge_materialize 6, stale_witness_parity 5, backfill 4,
    cli_wiring 3, effective_gates 3, no_double_record 3
- **`bcrt` in `test_followup_kind_roundtrip.sh` is a false positive.** It is a
  one-liner with no registration. Its only leftovers are the two deliberate
  per-user dirs described below.
- **2 suites the original sweep missed** because their array is named `TMPDIRS`.
  Both leak through `$(make_repo …)`:
  - `test_resolve_config_path_cli.sh` leaks 4 dirs.
  - `test_learn_wrappers.sh` leaks 3 dirs.
- **The refined sweep reproduces exactly these 21 suites.** It handles one-liner
  functions and any `*CLEANUP*`/`*TMPDIRS*` array. Its only other hit is t2031's
  own comment, which mentions `$(make_fixture)`.
- **Not this defect class, out of scope:**
  - `ait-test-cwd-<uid>` (`tests/lib/scratch_cwd.sh`) and `aitask-locks-<uid>-<n>`
    (`lib/stale_lock.sh`) are deliberate, stable-named per-user dirs.
  - `aitask_verify_build_*.log` files are written to `$TMPDIR` by
    `aitask_run_project_command.sh` by design.

## Approach: one registered root per suite

The task suggests t2031's result-variable pattern. Applied here, that would rewrite
about 200 call sites. Instead, give each suite **one temp root that is created and
registered in the suite's top-level shell**, and have every factory create its dir
*under* that root. (The task's diagnostic context already names "a shared parent
temp dir" as a valid cleanup route.)

Benefits:
- Every `X="$(helper)"` call site stays unchanged. Each helper changes in one line.
- It works whatever shell the factory runs in: `$( )`, `( … )` test bodies, or a
  future caller.
- Each suite's existing cleanup (an EXIT trap or a footer loop over the array)
  removes the root, and the fixtures go with it.

### 1. New lib `tests/lib/fixture_root.sh`

bash-3.2-safe, idempotent-source guard, same header style as `asserts.sh`. Source it
after `asserts.sh`.

- **`fixture_root_init [array_name]`** (default `CLEANUP_DIRS`)
  - Validates the name against `^[A-Za-z_][A-Za-z0-9_]*$` and refuses otherwise,
    so `eval` never sees untrusted text.
  - Creates the root with `mktemp -d "${TMPDIR:-/tmp}/ait_fixture_root_XXXXXX"`.
  - Resolves it with `cd … && pwd -P` into `FIXTURE_ROOT`. The physical path keeps
    `make_repo`'s own `pwd -P` and the macOS `/var` → `/private/var` case
    consistent.
  - Appends the root to the named array in the **calling** shell, and records the
    array name in `FIXTURE_ROOT_ARRAY`.
  - On failure it prints `FAIL:` and `exit 1`, the same shape as
    `assert_counters_init`.
- **`fixture_mktemp_d <prefix>`** runs `mktemp -d "$FIXTURE_ROOT/<prefix>_XXXXXX"`.
  It **fails closed**: if `FIXTURE_ROOT` is unset or not a directory, it writes a
  message naming `fixture_root_init` to stderr and returns 1 with empty stdout. It
  never falls back to `$TMPDIR`, because that fallback would silently bring the
  leak back.
- **`assert_fixture_registered <desc> <dir>`** is a single assertion built on
  `assert_eq "$desc" registered "$state"`. It checks, in order:
  1. `dir` is non-empty (t2031's vacuous-membership trap);
  2. `dir` is a directory;
  3. `FIXTURE_ROOT` is set;
  4. `dir` lies under `"$FIXTURE_ROOT"/`;
  5. `FIXTURE_ROOT` is an exact element of the `FIXTURE_ROOT_ARRAY` array
     (loop compare, not padded-substring).

  Any failed check sets `state` to a reason naming the check.

### 2. Migrate the 21 suites (same edit in each)

Each suite already has the order: `asserts.sh` sourced → `PASS=0` → `CLEANUP_DIRS=()`.

a. Source `fixture_root.sh` on the line after the `asserts.sh` source line, using the
   suite's own `$PROJECT_DIR/tests/lib/` form.

b. **Call `fixture_root_init` late, at top level, immediately before step d's
   assertion. That point is after every prerequisite check, skip exit and helper
   definition, and before the first fixture is allocated.** Do not place it next to
   the array init.
   - Use `fixture_root_init TMPDIRS` in `test_resolve_config_path_cli.sh` and
     `test_learn_wrappers.sh`.
   - Why: most of these suites clean up only in a footer loop (no EXIT trap). A root
     allocated before a successful-skip path would leak on that path.
     `test_skill_errexit_capture.sh` has exactly that path: `CLEANUP_DIRS=()` at
     line 41, `cd … || exit 1` at line 43, and a minijinja `exit 0` SKIP at line 50,
     with a footer-only cleanup loop.
   - An audit of the other footer-only suites found no other top-level exit between
     the planned init point and the footer verdict. For example,
     verification_stale's `cd "$PROJECT_DIR" || exit 1` at line 886 comes before its
     test-invocation block, so the init goes after it.
   - Re-check this during the edit for each suite: the init must sit after the
     suite's last top-level pre-test exit.

c. In the helper, replace the `mktemp -d …` and `CLEANUP_DIRS+=` pair with
   `tmp="$(fixture_mktemp_d <prefix>)" || return 1`.
   - Keep each helper's existing prefix. Bare `mktemp -d` helpers get a descriptive
     one (`test_amend_guard`, `test_verstale`, `test_resolvecfg`, `test_learnwrap`).
   - Add a one-line comment citing t2055, as t2031 did.
   - Helpers:
     - `new_fixture` in 14 suites
     - `fresh_tmpdir` and `make_repo` (atomic_task_file_writes)
     - `setup_repo` (amend_guard)
     - `new_dir` (skill_errexit_capture)
     - `new_repo` (verification_stale)
     - `make_repo` (resolve_config_path_cli, learn_wrappers)
   - `make_repo` in atomic keeps its `pwd -P` line. Directly-called helpers that
     register correctly are left alone (e.g. verification_stale's
     `setup_update_project` and `test_outside_a_git_repository_skips`).

d. Add one in-suite regression assertion at top level, through the `$( )` path that
   leaked:
   `assert_fixture_registered "<helper> dirs land under the registered FIXTURE_ROOT" "$(<helper> [args])"`
   - Place it directly after step b's `fixture_root_init`. Like the init, it comes
     after the helper and everything it depends on are defined, and before the first
     test runs.
   - The atomic suite gets one for each of its two helpers.
   - `make_repo` in learn_wrappers is called with `yes yes`.

### 3. New test `tests/test_fixture_root.sh`

It covers the library and adds a repo-wide guard. Self-contained `PASS`/`FAIL`
footer; it uses the lib itself for its own temp dirs.

**Lib behaviour**
- After init, the root exists, equals its `pwd -P`, and is in `CLEANUP_DIRS`.
- `d="$(factory)"` built on `fixture_mktemp_d` passes `assert_fixture_registered`.
- **Negative controls.** Each runs in a subshell with its own counters and must
  record `FAIL=1`:
  - an old-shape factory (TMPDIR `mktemp` plus `CLEANUP_DIRS+=` inside `$( )`);
  - an empty dir argument;
  - a dir outside the root;
  - a root dropped from the array.
- `fixture_mktemp_d` with `FIXTURE_ROOT` unset gives rc≠0, empty stdout, and stderr
  naming `fixture_root_init`.
- A custom array name (`TMPDIRS`) works. An invalid name (`'x;y'`) is refused and
  defines nothing.
- **End-to-end probe.** Generate two tiny suites with a probe `TMPDIR` and a trap
  cleanup:
  - new shape, 3 `$(factory)` calls → 0 leftovers;
  - old shape (control) → 3 leftovers. This proves the probe can see a leak.

**Guard**
- An awk scanner over `tests/*.sh` and `tests/lib/*.sh`:
  - It finds functions whose body appends to a `*CLEANUP*`/`*TMPDIRS*` array.
    Bodies run from `name() {` to `^}`. One-liner definitions with balanced braces
    count as their own body.
  - It reports each such function that is called as `$( name` on a non-comment
    line.
- The live tree must have zero hits. The failure message names the file and
  function and points to `tests/lib/fixture_root.sh`.
- **Scanner controls** on synthetic files:
  - flagged: the old shape; the `TMPDIRS` variant;
  - not flagged: a direct-call helper, a `bcrt`-style one-liner followed by a
    distant top-level registration, and a comment that mentions `$(helper)`.

## Verification

1. Probe all 21 suites after the change, with the same probe script
   (`TMPDIR=<empty dir>`):
   - every suite exits 0 with all tests passing;
   - **0 fixture-class leftovers** per suite;
   - only the deliberate `ait-test-cwd-*` / `aitask-locks-*` dirs and the
     run_project_command build logs remain, the same as the baseline.
   - Record the before and after counts in Final Implementation Notes.
1b. **Probe the forced-skip path.** Run
   `AIT_PYTHON=/usr/bin/python3 TMPDIR=<empty dir> bash tests/test_skill_errexit_capture.sh`.
   The system Python 3.14 has no minijinja, which I checked.
   - Expect the SKIP line, rc 0, and **no `ait_fixture_root_*` leftover**.
   - Same probe on the pre-change tree as a baseline.
   - Control: a scratch copy that calls `fixture_root_init` right after the array
     init must leave one `ait_fixture_root_*` leftover on the same skip path. This
     proves the probe can see that leak.
2. `bash tests/test_fixture_root.sh` passes.
3. **Red proofs, in scratch copies only** (never by stash or git-restore of live
   files):
   - Revert one suite's helper to the old shape. Its new
     `assert_fixture_registered` must fail with rc≠0.
   - The guard must flag that copy when pointed at a dir containing it.
4. `test_followup_kind_roundtrip.sh` is untouched. Its probe stays at 2 non-class
   leftovers.
5. `shellcheck` on the new lib, the new test and the 21 suites: no new warnings
   compared with the baseline.

## Step 9

Commit the code as `bug: Register test fixtures under a per-suite root so $( ) factories stop leaking (t2055)`,
naming the paths explicitly. Commit the plan separately via `aitask_task_commit.sh`.
Archive through the standard Step 9 flow, on the current branch (profile `fast`,
no worktree).

## Risk

### Code-health risk: low
- 21 test files change at once. A suite could depend on its fixture's parent being
  `$TMPDIR` itself (sibling paths, "outside a repo" checks). I checked for this:
  - no suite references its fixture prefix outside the helper;
  - the root is a plain non-repo dir.

  Severity: low. → mitigation: none needed (Verification 1 reruns every suite).
- The guard is a heuristic awk and could false-positive on a future helper shape.
  Severity: low. → mitigation: none needed (its controls pin the known
  false-positive shapes, and its message names the remedy).

- A root allocated before a suite's successful-skip exit would leak in footer-only
  suites (`test_skill_errexit_capture.sh`'s minijinja SKIP). Severity: medium
  (residual — addressed in the plan body). → mitigation: none needed:
  - step 2b's late-init placement rule and per-suite exit audit;
  - Verification 1b's forced-skip probe with a positive control.

### Goal-achievement risk: low
None identified. The leak is measured directly before and after for every suite.
The per-suite assertion and the repo-wide guard prevent regressions, including in
suites not yet written.

## Post-Review Changes

### Change Request 1 (2026-10-19 11:40)
- **Requested by user:** `assert_fixture_registered`'s membership loop ended in `[[ "$d" == "$FIXTURE_ROOT" ]] && found=1`. When the root was followed by any other cleanup entry, the loop (and so the `eval`) returned 1, and a `set -e` suite exited silently before `assert_eq` ran. Reproduced: `CLEANUP_DIRS=("$FIXTURE_ROOT" "$other")` under `set -e` gave rc=1 with no output. Six migrated suites run under `set -e`.
- **Changes made:**
  - The loop body is now `if [[ … ]]; then found=1; fi`, so the loop always succeeds and `found` alone decides membership. A comment records why.
  - New regression in `tests/test_fixture_root.sh`: an errexit child script runs the assertion with the root followed by another entry, and with the root last. Each must print `reached PASS=1 FAIL=0` with rc 0.
  - Red proof: against a scratch copy of the lib with the old loop, the root-first case fails (`got '1|'`), 29/30.
  - The regression's heredoc first wrote the append as `CLEANUP_DIRS+=(`. The live-tree guard flagged that as a registering function called in `$( )`, so it now uses `CLEANUP_DIRS=("${CLEANUP_DIRS[@]}" …)`.
- **Files affected:** `tests/lib/fixture_root.sh`, `tests/test_fixture_root.sh`

## Final Implementation Notes
- **Actual work done:**
  - New `tests/lib/fixture_root.sh`. `fixture_root_init [array]` creates one physical-path root per suite and registers it in the calling shell. `fixture_mktemp_d <prefix>` fails closed when there is no root. `assert_fixture_registered <desc> <dir>` is a single assertion, with the emptiness check first.
  - **20 suites (21 helpers)** migrated:
    - Each helper's `mktemp -d` + `CLEANUP_DIRS+=` pair is replaced by `fixture_mktemp_d <prefix> || return 1`. Every `X="$(helper)"` call site is unchanged.
    - Each suite sources the lib after `asserts.sh`.
    - Each suite calls `fixture_root_init` at top level just before its first test, then makes one `assert_fixture_registered` call through `$(helper)`. The atomic suite asserts both of its helpers.
  - New `tests/test_fixture_root.sh` (30 assertions):
    - library behaviour, including the negative controls and custom array names;
    - `set -e` membership regressions;
    - end-to-end probe-TMPDIR leak checks with controls, including a SKIP-path control;
    - a repo-wide guard: an awk scanner over `tests/*.sh` and `tests/lib/*.sh`, with five scanner controls.
- **Deviations from plan:**
  - The count is 20 suites / 21 helpers, not "21 suites". `test_atomic_task_file_writes` has two helpers.
  - `test_gates_sync_registry.sh` pins its own assertion count (`"92" "$TOTAL"`), which the new assertion moved to 93. No other migrated suite pins a count.
  - The new test's file-wide `shellcheck disable=SC2030,SC2031,SC2016` must sit before the first command to apply file-wide.
- **Issues encountered:**
  - Plan review: initializing the root right after the array init would leak it on `test_skill_errexit_capture.sh`'s minijinja SKIP `exit 0`, since that suite cleans up only in its footer. Init moved to just before the first test.
  - Code review: the membership loop's `[[ … ]] && found=1` tail killed `set -e` suites when the root was not the last array entry. See Post-Review Changes.
  - One background probe run of `test_atomic_task_file_writes.sh` hit a 900s timeout inside its `aitask_projects.sh: registry rewrite` section, which this change does not touch. Seven reruns (5 live, 1 live in parallel with a HEAD copy, 1 in the final full probe) all completed in about 2s, 64/64. Unexplained and not reproduced.
- **Key decisions:**
  - A per-suite registered root instead of t2031's result-variable pattern. Every `$( )` call site (about 200) stays valid, and a future `$( )` or `( … )` caller cannot reintroduce the leak.
  - The guard reads function bodies as text, so test fixtures that spell a registration are `|`-prefixed and stripped with `sed`. For the same reason, the `set -e` regression appends with `CLEANUP_DIRS=("${CLEANUP_DIRS[@]}" …)`.
- **Verification (durable evidence)**, measured with `TMPDIR=<empty dir> bash tests/<suite>.sh`:
  - **Before, leaked fixture dirs per run:**
    - gate_verifiers 60, gates_sync_registry 28, skill_errexit_capture 24, gate_orchestrator 18, verification_stale 18 (tmp.*), atomic_task_file_writes 15 (8 probe + 7 sites), gate_active_gates 14
    - amend_guard 10 (tmp.*), gate_procedure_docs 10, gate_risk_verifier 10, gate_pass 6, web_merge_materialize 6, stale_witness_parity 5, declaration_backfill 4, resolve_config_path_cli 4, effective_gates 3, cli_wiring 3, no_double_record 3, learn_wrappers 3
    - run_project_command: many `test_runprojcmd_*` dirs, plus build logs.
  - **After (final probe, post review fix):** all 20 suites, `test_followup_kind_roundtrip` and `test_fixture_root` have rc=0, no FAIL lines, and **0 fixture leftovers**. Only the deliberate `ait-test-cwd-<uid>` / `aitask-locks-*` dirs and run_project_command's `aitask_verify_build_*.log` remain.
  - **Forced-skip path** (`AIT_PYTHON=/usr/bin/python3`, no minijinja), `test_skill_errexit_capture.sh`:
    - before: rc 0, SKIP, no root;
    - after: rc 0, SKIP, no root;
    - control copy with init right after the array init: leaves 1 `ait_fixture_root_*` dir.
  - **Red proofs:**
    - A copy of `test_gate_cli_wiring.sh` with the old helper shape gives rc=1, `FAIL: new_fixture dirs land under the registered FIXTURE_ROOT (… got 'outside FIXTURE_ROOT …')`. The guard flags all 4 `$(new_fixture)` sites in that copy.
    - The guard over the HEAD versions of all `tests/*.sh` and `tests/lib/*.sh` flags exactly the 21 helpers: no `bcrt`, and no hit on t2031's comment.
    - The `set -e` regression against the old loop: 29/30, `got '1|'`.
  - **Other checks:** `test_cd_guard_lint.sh` passes 92/92. `shellcheck`: the new files are clean. Each migrated suite gains only one SC1091 info note for the new `source` line, the same note its `asserts.sh` line already gets.
- **Upstream defects identified:** None
- **Not in this class (observations, not defects):** `aitask_run_project_command.sh` writes `aitask_verify_build_*.log` to `$TMPDIR` by design, so `test_run_project_command.sh` leaves those logs behind. The `ait-test-cwd-<uid>` and `aitask-locks-<uid>-<cksum>` dirs are deliberate persistent per-user namespaces. `bcrt` (`test_followup_kind_roundtrip.sh`) was a heuristic false positive.
