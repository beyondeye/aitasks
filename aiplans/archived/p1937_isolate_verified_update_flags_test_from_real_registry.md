---
Task: t1937_isolate_verified_update_flags_test_from_real_registry.md
Base branch: main
Output branch: main
---

# t1937 — Isolate `test_verified_update_flags.sh` from the real registry

## Context

`tests/test_verified_update_flags.sh` runs `aitask_verified_update.sh` with
`cd "$PROJECT_DIR"`, so each run writes a `test_414_flags` verified score into the
real `aitasks/metadata/models_claudecode.json`, then commits it and pushes it to
`origin/aitask-data`. Origin now holds 87 junk runs on `opus4_6` and 3 on
`opus4_7_1m`. Because the result depends on the live data branch, the test is also
flaky: when the branch had diverged, the first call returned
`UPDATED_REMOTE_ONLY` (exit 3), and `set -e` stopped the file before any
assertion ran.

`tests/test_verified_update.sh` and `tests/test_usage_update.sh` already run in
throwaway repos (`tests/lib/metadata_update_fixture.sh`,
`tests/lib/test_scaffold.sh`). This plan moves the flags test onto the same
fixtures. A grep of `tests/*.sh` finds no other file that runs an updater in
`$PROJECT_DIR`; `test_skill_render_task_workflow.sh` only matches the script
names as strings.

## Implementation

### 1. `tests/lib/metadata_update_fixture.sh` — add a public no-remote fixture

The lib documents itself as shared and exports only public setup functions
(`setup_remote_metadata_repo`, `setup_branch_mode_metadata_repo`). The no-remote
variant exists only as a private copy inside `test_verified_update.sh`. Add it to
the lib's legacy-mode section, next to `setup_remote_metadata_repo`:

```bash
# setup_local_metadata_repo <script_basename>
# Echoes <repo_dir>: a legacy-mode checkout with NO remote, so an update
# commits locally and never pushes anywhere.
setup_local_metadata_repo() {
    local script="$1" repo_dir
    repo_dir="$(mktemp -d)"
    (
        cd "$repo_dir" || exit 1
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        _mdfix_populate "$repo_dir" "$script"
        git add .
        git commit -m "Initial setup" --quiet
    )
    echo "$repo_dir"
}
```

Also add this function to the header comment that lists the lib's helpers.
`test_verified_update.sh`'s private `setup_repo` stays as it is; converting it is
out of scope.

### 2. `tests/test_verified_update_flags.sh` — rewrite on the fixture

- Header: keep the description and add a short note on why every call runs in a
  scaffolded repo with no remote (t1937).
- Keep `unset AITASK_AGENT_STRING`.
- Use the same preamble as `test_verified_update.sh`:
  - `scratch_cwd.sh` + `enter_scratch_cwd`
  - `test_scaffold.sh`
  - `asserts.sh`
  - `metadata_update_fixture.sh`
- Drop `set -e`. Capture each exit status explicitly as `rc=0; out=$(…) || rc=$?`.
  This fixes the run that died before reaching any assertion.
- Build one fixture: `REPO="$(setup_local_metadata_repo aitask_verified_update.sh)"`.
  - Copy `aitask_resolve_detected_agent.sh` into `$REPO/.aitask-scripts/`. The
    `--agent/--cli-id` path needs it; `test_verified_update.sh:971` copies it the
    same way.
  - Remove the fixture on exit with `trap 'rm -rf "$REPO"' EXIT`.
  - Guard assertion: `git -C "$REPO" remote` is empty, so nothing can be pushed.
- Run every call as `(cd "$REPO" && ./.aitask-scripts/aitask_verified_update.sh …)`.
  Nothing references `$PROJECT_DIR`'s scripts or cwd at run time.
- Assertions. The fixture is deterministic, so the checks can be exact; the seed
  row is `opus4_6` / `claude-opus-4-6`:
  1. `--agent claudecode --cli-id claude-opus-4-6 --skill test_414_flags --score 5`:
     - rc 0
     - output contains `UPDATED:claudecode/opus4_6:test_414_flags:100`
     - the fixture JSON has `.models[0].verified.test_414_flags == 100`. This shows
       the write went into the fixture.
  2. `--agent-string claudecode/opus4_6 … --score 4`:
     - rc 0
     - output contains `UPDATED:claudecode/opus4_6:test_414_flags:90`
     - `verifiedstats.test_414_flags.all_time.runs == 2`
  3. Four rejection cases: mutual exclusion, `--agent` without `--cli-id`,
     `--cli-id` without `--agent`, and neither flag. Each one keeps its existing
     message assertion and adds:
     - rc ≠ 0 (`assert_exit_nonzero_rc`)
     - the fixture registry is byte-identical to a snapshot taken before the
       rejection cases (`cmp -s`)
- Footer: use the `Results:` / `ALL TESTS PASSED` block from
  `test_verified_update.sh`, with exit 1 on any failure.

### 3. Registry cleanup → follow-up task, not this commit

The task makes cleanup optional and asks for "a separate, reviewed commit". I
recommend leaving it out of this task:

- The local `aitask-data` branch is out of sync right now. It has 42 unpushed
  commits and 7 unpulled ones, and unstaged changes are blocking the rebase.
  Origin's junk on `opus4_6` (87 runs) also differs from the local copy (85 runs).
- Deleting the key locally would conflict with origin's edits to the same JSON
  rows when the branch is rebased.
- The registry has concurrent writers going through `lib/registry_cas.sh`, so a
  hand edit with `jq` could lose their writes.

Instead, after this task is approved, create a follow-up with
`aitask_create.sh --batch`. It removes `verified.test_414_flags` and
`verifiedstats.test_414_flags` from every row of `models_claudecode.json`
(currently `opus4_6` and `opus4_7_1m`) once the data branch is reconciled
(`ait syncer`), using a compare-and-swap rewrite.

## Verification

- `bash tests/test_verified_update_flags.sh` → all PASS, exit 0.
- Run it twice and check that the real `models_claudecode.json` keeps the same
  `test_414_flags` run counts. `git -C .aitask-data log -1 --
  aitasks/metadata/models_claudecode.json` should show no new
  `test_414_flags` commit.
- Negative control: temporarily point one call back at `$PROJECT_DIR` in a
  scratch copy of the test (not in the repo). The fixture-JSON assertion should
  fail, which shows the new assertions catch the old defect. Run it against a
  scratch copy so the real registry is never written.
  - Simpler alternative: break the copied resolver in the fixture and confirm
    test 1 fails.
- Regression: `bash tests/test_verified_update.sh` and
  `bash tests/test_usage_update.sh` pass. Both source the edited fixture lib.
- `shellcheck tests/test_verified_update_flags.sh tests/lib/metadata_update_fixture.sh`.

## Step 9 (Post-Implementation)

Commit the code (`test:` type), then archive via the standard Step 9 flow. The
cleanup follow-up from §3 is created before archival.

## Risk

### Code-health risk: low
- Adding a public function to a shared fixture lib that three suites source could clash with an existing name · severity: low · → mitigation: none needed. The name `setup_local_metadata_repo` is new (grep), and the regression runs of both sibling suites cover it.

### Goal-achievement risk: low
- None identified.

## Final Implementation Notes
- **Actual work done:** Added `setup_local_metadata_repo <script>` (no-remote, legacy-mode fixture) to `tests/lib/metadata_update_fixture.sh` and generalized the lib header ("Every setup_* helper echoes…"). Rewrote `tests/test_verified_update_flags.sh` on it: scratch-cwd preamble, one fixture repo (+ copied `aitask_resolve_detected_agent.sh`) removed by an EXIT trap, a `run_update` helper capturing `OUT`/`RC`, a no-remote guard assertion, exact `UPDATED:…:100` / `:90` tokens, fixture-JSON checks, explicit rc checks, and a byte-identical-registry check after each of the four rejection cases. 19 assertions, all pass.
- **Deviations from plan:** Commit type is `bug:` (the task's `issue_type`), not `test:` as the plan's Step 9 note said — the commit-type convention takes the issue_type. The registry snapshot comparison uses `assert_eq` on `cat` output rather than `cmp -s`, which gives a readable diff on failure.
- **Issues encountered:** None in the change itself. `tests/test_cd_guard_lint.sh` fails on the live tree, but every violation it lists is in other files (`test_add_model.sh`, `test_setup_hooks_only.sh`, `test_aitasks_home.sh`, …), several of which are being edited by concurrent sessions — none in the files touched here.
- **Key decisions:** No-remote fixture (not `setup_remote_metadata_repo`): the test only exercises flag parsing/resolution, and a remote-less repo makes "never pushes" structural. The registry cleanup was deferred to a follow-up task (data branch currently diverged; concurrent CAS writers). Verification: real registry `test_414_flags` run counts unchanged (85 / 3) across two runs, no new data-branch registry commit; negative controls — writes redirected to another repo (old-defect shape) → 2 FAIL; broken resolver → 5 FAIL; `test_verified_update.sh` and `test_usage_update.sh` pass on the edited lib.
- **Upstream defects identified:** None
