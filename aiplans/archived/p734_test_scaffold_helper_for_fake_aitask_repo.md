---
Task: t734_test_scaffold_helper_for_fake_aitask_repo.md
Base branch: main
plan_verified: []
---

# Plan: Test-Scaffold Helper for Fake `.aitask-scripts/` Repos (t734)

## Context

`./ait` and most helper scripts unconditionally source three "system" libs at
startup: `lib/aitask_path.sh`, `lib/python_resolve.sh`, `lib/terminal_compat.sh`.
When a test scaffolds a fake `.aitask-scripts/lib/` directory but skips any of
these, the next call into `./ait` (or a helper that learns to source another
of them) crashes with `No such file or directory`. This is the time-bomb
pattern surfaced by t732_5 (which patched only the 4 originally-failing
tests).

A fresh audit on `main`:

```
TESTS THAT mkdir lib: 43
  33 path=N py=N term=Y    (highest risk — only terminal_compat copied)
   6 path=Y py=Y term=Y    (already covers all three — DRY ports only)
   2 path=Y py=N term=Y    (missing python_resolve)
   2 path=N py=Y term=Y    (missing aitask_path)
```

The task description's "51 affected tests" reflects pre-cleanup state. The
real number of scaffolders today is **43**, of which **37** are at risk and
**6** are cosmetic ports.

Goal: converge the scaffolding pattern behind a single helper
(`tests/lib/test_scaffold.sh`) that always copies the three system libs,
port all 43 scaffolders to use it, verify zero whole-suite regressions, and
add a CLAUDE.md guardrail so future system-lib dependencies get added to the
helper in the same PR.

## Step 1 — Write `tests/lib/test_scaffold.sh`

New file. The helper takes a destination directory and copies the three
system libs into `<dst>/.aitask-scripts/lib/`. Idempotent (`mkdir -p`). The
caller is responsible for setting `PROJECT_DIR` before sourcing — this
mirrors the existing `tests/lib/venv_python.sh` convention which assumes
`PROJECT_DIR` is in scope at use-time.

```bash
#!/usr/bin/env bash
# test_scaffold.sh - Bootstrap a minimal fake .aitask-scripts/ tree.
# Always copies the "system" libs that ./ait and most helpers source
# unconditionally. Caller adds script-specific files on top.
#
# REQUIRES: PROJECT_DIR (path to the real aitasks repo root) is set in
# the caller's scope before invoking setup_fake_aitask_repo().
# shellcheck disable=SC2034  # may be referenced externally

if [[ -z "${_AIT_TEST_SCAFFOLD_LOADED:-}" ]]; then
    _AIT_TEST_SCAFFOLD_LOADED=1

    setup_fake_aitask_repo() {
        local repo_dir="$1"
        mkdir -p "$repo_dir/.aitask-scripts/lib"
        cp "$PROJECT_DIR/.aitask-scripts/lib/aitask_path.sh"     "$repo_dir/.aitask-scripts/lib/"
        cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" "$repo_dir/.aitask-scripts/lib/"
        cp "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"  "$repo_dir/.aitask-scripts/lib/"
    }
fi
```

Convention follows `tests/lib/venv_python.sh` (double-source guard via
`_AIT_*_LOADED`, `shellcheck disable=SC2034`).

## Step 2 — Port the 43 scaffolders

For each affected test, replace the current pattern:

```bash
mkdir -p [<dir>/].aitask-scripts/lib
cp "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh" [<dir>/].aitask-scripts/lib/
# … and optionally aitask_path.sh, python_resolve.sh …
```

with:

```bash
# shellcheck source=lib/test_scaffold.sh
. "$SCRIPT_DIR/lib/test_scaffold.sh"   # once, near the top — after PROJECT_DIR is set
setup_fake_aitask_repo "<dst>"          # at each scaffold site
```

Where `<dst>` matches the variable the surrounding code already uses (`$PWD`,
`$repo_dir`, `$tmpdir`, `$PROJECT_TEST_DIR`, `$upstream_dir`, `$local_dir`,
etc.).

The three system-lib `cp` lines are then removed. **Domain-specific** lib
copies (`task_utils.sh`, `archive_utils.sh`, `agentcrew_utils.sh`,
`pid_anchor.sh`, `archive_scan.sh`, `launch_modes_sh.sh`, `launch_modes.py`,
`repo_fetch.sh`, etc.) stay on top, because they vary per test.

Tests with **multiple scaffold sites** (e.g., `test_contribute.sh`,
`test_task_push.sh`, `test_init_data.sh`) get `setup_fake_aitask_repo` called
at each site; the source line is added once at the top. The helper is
idempotent so re-invocation across sites is safe.

**The 43 tests to port** (verified via `grep -l "mkdir.*\.aitask-scripts/lib"
tests/test_*.sh`):

`test_aitask_path_resolution.sh`, `test_archive_carryover.sh`,
`test_archive_followups_block.sh`, `test_archive_folded.sh`,
`test_archive_force.sh`, `test_archive_no_overbroad_add.sh`,
`test_archive_related_issues.sh`, `test_archive_release_lock.sh`,
`test_auto_merge_file_ref.sh`, `test_aw_carryover.sh`,
`test_brainstorm_cli.sh`, `test_brainstorm_init.sh`,
`test_brainstorm_run_history.sh`, `test_change_meta.sh`,
`test_claim_id.sh`, `test_codeagent.sh`, `test_contribute.sh`,
`test_create_silent_stdout.sh`, `test_crew_init.sh`,
`test_crew_setmode.sh`, `test_crew_template_includes.sh`,
`test_explain_context.sh`, `test_explain_runs.sh`,
`test_external_python_install.sh`, `test_file_references.sh`,
`test_fold_content.sh`, `test_init_data.sh`,
`test_init_legacy.sh`, `test_init_skill.sh`, `test_issue_update.sh`,
`test_label_filter.sh`, `test_launch_mode_field.sh`,
`test_lock_diag.sh`, `test_lock_force_cleanup.sh`,
`test_lock_remote_handling.sh`, `test_pr_close.sh`,
`test_skill_verify_yaml_helper.sh`, `test_swap.sh`,
`test_swap_task_data.sh`, `test_syncer.sh`, `test_task_push.sh`,
`test_unrolled_skills.sh`, `test_wrap.sh`.

(Final list is regenerated at implementation time from the actual grep,
since new tests may have landed.)

Port in batches of ~10. After each batch, run the regression loop in Step 3.

## Step 3 — Regression check

After each batch, and finally after all batches:

```bash
PASS=0; FAIL=0; FAILED=()
for t in tests/test_*.sh; do
    if bash "$t" >/dev/null 2>&1; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        FAILED+=("$t")
    fi
done
echo "PASS: $PASS  FAIL: $FAIL"
[[ $FAIL -gt 0 ]] && printf '  %s\n' "${FAILED[@]}"
```

**Baseline first:** run this loop on `main` BEFORE Step 2 starts, to capture
the current PASS/FAIL set. Some tests fail on `main` for unrelated reasons
(`./ait` data-branch fixtures, network-dependent flows). The acceptance bar
is **no NEW failures introduced by the port** — not "100% pass."

If a ported test newly fails, the helper baseline is missing a lib for that
test's scenario. Either:
- Add the missing dependency to the helper (if it's another system lib that
  `./ait` sources unconditionally), OR
- For that single test, restore the missing `cp` line on top of
  `setup_fake_aitask_repo` (the helper is the floor, not a ceiling).

## Step 4 — CLAUDE.md guardrail

Add a one-paragraph entry under the existing "## Shell Conventions" section
(or as a new "## Test Authoring" section if it grows). Wording draft:

> **System libs added to `./ait`'s source-on-startup chain must be added to
> `tests/lib/test_scaffold.sh::setup_fake_aitask_repo()` in the same PR.**
> 43 tests scaffold a fake `.aitask-scripts/lib/` via this helper; missing
> entries crash every one of them with `No such file or directory` the next
> time `./ait` (or any helper that learns to source the new lib) is invoked
> from the fake repo. Current baseline: `aitask_path.sh`,
> `terminal_compat.sh`, `python_resolve.sh`.

The exact insertion point is the Shell Conventions block in `CLAUDE.md`,
right after the `sed_inplace` note — it's the closest neighbour for
test/portability concerns.

## Critical files

- **New:** `tests/lib/test_scaffold.sh`
- **Modified:** 43 files under `tests/test_*.sh` (see Step 2 list)
- **Modified:** `CLAUDE.md` (one-paragraph guardrail entry)

## Verification

1. `tests/lib/test_scaffold.sh` exists with `setup_fake_aitask_repo()` and
   the three system-lib copies.
2. `grep -l "mkdir.*\.aitask-scripts/lib" tests/test_*.sh | wc -l` returns
   `0` (or only the helper itself + any deliberately exempted tests).
3. `grep -l "setup_fake_aitask_repo" tests/test_*.sh | wc -l` matches the
   number of ported tests (43, minus any deliberate exemptions).
4. Whole-suite regression loop (Step 3 driver) reports no NEW failures vs
   the pre-port baseline captured before Step 2.
5. CLAUDE.md guardrail entry is present and mentions the helper by name.

## Step 9 — Post-Implementation

See task-workflow Step 9 for the standard cleanup/archival/merge sequence.
This task works on the current branch (profile `fast`, `create_worktree:
false`), so the worktree-removal sub-step is a no-op.

## Out of scope

- Porting tests that don't scaffold `.aitask-scripts/lib/` (e.g.,
  `test_python_resolve.sh`, `test_skill_render.sh`, `test_no_recurse.sh` —
  they reference paths but don't scaffold a fake repo).
- Auto-discovering system libs by reflection (explicit copy list is more
  debuggable).
- Refactoring domain-specific lib copies (`task_utils.sh`, `archive_utils.sh`,
  etc.) — those vary per test by design.
- Fixing unrelated pre-existing test failures surfaced by the baseline run.

## Final Implementation Notes

- **Actual work done:** Created `tests/lib/test_scaffold.sh` with
  `setup_fake_aitask_repo()` (copies `aitask_path.sh`, `terminal_compat.sh`,
  `python_resolve.sh`). Ported 43 scaffolder tests via a one-shot Python
  porter (`/tmp/port_scaffolders.py`, ephemeral — not committed). Added a
  CLAUDE.md bullet under "Shell Conventions" referencing the helper.
  Baseline: 110 PASS / 11 FAIL. Post-port: 110 PASS / 11 FAIL — identical
  failure set, all pre-existing and unrelated (tmux / opencode_setup /
  skill_verify infrastructure).
- **Deviations from plan:** None substantive. The plan estimated 43
  scaffolders from a fresh audit; the porter confirmed exactly 43.
- **Issues encountered:**
  - `test_find_files.sh` failed after the port because the helper added
    `python_resolve.sh` to a directory the test treats as searchable test
    data — the new file outranked `task_utils.sh` for a "resolve task" query.
    Fix: restored the test's original scaffold pattern with a NOTE comment
    explaining the deliberate bypass. The helper-as-floor model accepts this
    case-by-case opt-out.
  - `test_contribute.sh` failed because the porter's "look ahead for next
    cp line to derive the destination" heuristic mis-attributed the upstream
    `mkdir` (which had no lib copies of its own) to `$local_dir`. Fix:
    manually restored the upstream mkdir to its original form. The helper
    site for `$local_dir` and `$PROJECT_TEST_DIR` (line 614) was correct.
  - `test_init_data.sh` uses `TEST_SCRIPT_DIR` instead of `SCRIPT_DIR`, so
    the porter's PROJECT_DIR-line regex didn't match — the source line was
    not auto-inserted. Fixed manually.
- **Key decisions:**
  - Used `"$PROJECT_DIR/tests/lib/test_scaffold.sh"` as the source path
    (rather than `"$SCRIPT_DIR/lib/..."`) so all 43 tests use the same
    incantation regardless of which `*_SCRIPT_DIR` variable they define.
  - When a `mkdir -p` line listed `.aitask-scripts/lib` alongside other
    directories, the porter strips just that token and keeps the line for
    the remaining dirs — preferable to dropping the whole mkdir.
  - Helper baseline kept to the three actually-system libs. Domain libs
    stay in each test's cp list.
- **Upstream defects identified:** None.

Note: the one-shot port script lived at `/tmp/port_scaffolders.py` for the
duration of this task; it is intentionally not committed (single-use,
content embedded in the porter's logic above for reference).
