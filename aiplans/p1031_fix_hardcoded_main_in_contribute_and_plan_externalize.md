---
Task: t1031_fix_hardcoded_main_in_contribute_and_plan_externalize.md
Base branch: main
plan_verified: []
---

# Plan: t1031 — Fix hardcoded `main` in contribute + plan_externalize

## Context

t1027 fixed the hardcoded `main` primary-branch assumption in `desync_state.py`
and the syncer, but its plan review surfaced the **same defect class** in two
unrelated scripts. In a `master`-default repo (e.g. the sibling
`aitasks_mobile` project) these silently misbehave:

- **`aitask_contribute.sh`** — clone/project contribution mode diffs against the
  literal `main`. Where `main` doesn't exist the diff returns nothing (`|| true`
  swallows the error), so contribution mode **silently finds no changed files**.
- **`aitask_plan_externalize.sh`** — always writes `Base branch: main` into the
  plan metadata header (and only suppresses the `Branch:` line when the current
  branch equals the literal `main`), so the plan header **records the wrong base
  branch**.

Root cause is identical to t1027: a hardcoded `"main"` literal where the repo's
actual primary branch should be resolved dynamically. The reusable building
block is the resolution order already encoded in
`desync_state.py:detect_primary_branch` (origin/HEAD symbolic-ref → local
`main`→`master` probe → `"main"` fallback).

**Decision (user-chosen):** implement a **pure-bash** primary-branch resolver
(no python subprocess; keeps `plan_externalize` python-free, simpler test
fixtures), and keep it honest with the Python twin via **bidirectional
cross-reference comments** in both files (the maintainer guard against drift).

Out of scope (intentionally **not** changed):
- `create_new_release.sh:30` — root-level framework release tool; this repo is
  main-default; excluded per the task.
- `aitask_contribute.sh:168/223/278` — these build URLs to the **upstream**
  repo (`beyondeye/aitasks`, main-default) for downstream-mode fetch/links; they
  reference the *upstream* default branch, not the local primary branch.

## New shared helper — `.aitask-scripts/lib/git_utils.sh`

New sourced lib (guard against double-source like the other libs). Pure-bash,
mirrors `desync_state.py:detect_primary_branch` resolution order:

```bash
#!/usr/bin/env bash
# git_utils.sh - Shared git helpers for aitask scripts. Source; do not execute.
[[ -n "${_AIT_GIT_UTILS_LOADED:-}" ]] && return 0
_AIT_GIT_UTILS_LOADED=1

# Resolve the repository's primary branch name dynamically, against $PWD
# (callers cd to the repo root). Order: origin/HEAD symbolic-ref → local
# main→master probe → "main" fallback. Keeps "main" as the logical default so
# main-default repos are unchanged; master-default repos resolve correctly.
#
# MAINTAINER GUARD: this is the bash twin of
# .aitask-scripts/lib/desync_state.py:detect_primary_branch — keep the two
# resolution orders in sync. (t1031)
detect_primary_branch() {
    local head
    head="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null || true)"
    head="${head#origin/}"
    if [[ -n "$head" ]]; then
        printf '%s\n' "$head"
        return 0
    fi
    local candidate
    for candidate in main master; do
        if git rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    printf 'main\n'
}
```

Add the reciprocal guard comment to
`.aitask-scripts/lib/desync_state.py:detect_primary_branch` (docstring) pointing
back to `lib/git_utils.sh:detect_primary_branch`.

## Wire the helper into both scripts

- `aitask_contribute.sh` — after the existing `source .../lib/repo_fetch.sh`
  (line ~15): `source "$SCRIPT_DIR/lib/git_utils.sh"`.
- `aitask_plan_externalize.sh` — after `source "$SCRIPT_DIR/lib/terminal_compat.sh"`
  (line ~46): `source "$SCRIPT_DIR/lib/git_utils.sh"`.

Both already define `SCRIPT_DIR` = `.aitask-scripts`.

## Fix sites

**`aitask_contribute.sh`** — both clone/project local-diff sites (the task named
`:448`; `:479` in `generate_diff` is the identical defect in the same family):
- `list_changed_files` (~446-448): resolve `local primary; primary="$(detect_primary_branch)"`,
  then `git diff --name-only "$primary" -- "${dirs[@]}"`.
- `generate_diff` (~478-479): same, then `git diff "$primary" -- "${file_list[@]}"`.

**`aitask_plan_externalize.sh` `build_header`** (~248-310):
- After `current_branch=...` (line 250): `local primary; primary="$(detect_primary_branch)"`.
- Line 303: `"$current_branch" != "main"` → `"$current_branch" != "$primary"`.
- Line 307: `echo "Base branch: main"` → `echo "Base branch: $primary"`.

## Tests

1. **`tests/test_git_utils.sh`** (new, mirrors `tests/lib/asserts.sh` style) —
   source `git_utils.sh`, call `detect_primary_branch` with cwd set to each
   fixture:
   - main-default git repo → `main`
   - master-default repo (branch `master`, no `main`) → `master` (local probe path)
   - master-default with `origin/HEAD` → `origin/master` set → `master` (symbolic-ref path)
   - non-git directory → `main` (fallback)

2. **`tests/test_contribute.sh`** —
   - Required: `cp` `git_utils.sh` into the **two existing** fixture lib dirs
     (the clone `setup()` and `project_test`), since `contribute.sh` now sources
     it at startup (script-local source-on-startup ↔ scaffold rule — omitting it
     would crash every contribute test).
   - New: add a `master`-default project fixture (branch `master`, no `main`, a
     committed change on a `working` branch) and assert
     `--list-changes --target project --area <area>` **finds the changed file**
     (fails before the fix — diff vs missing `main` returns nothing — passes
     after). Mirrors existing Test 33.

3. **`tests/test_plan_externalize.sh`** — new test: `new_sandbox` + `git init`
   with `master` as the only branch, run the real externalize, assert the header
   contains `Base branch: master` (and no stray `Branch:` line, since
   current==primary). No fixture lib copies needed — the test runs the real
   script in place (`$SCRIPT_DIR` = real repo), only `$PWD` is the sandbox.

## Risk

### Code-health risk: low
- New lib sourced by two scripts; logic duplicated across bash/python ·
  severity: low · → mitigation: bidirectional cross-reference comments + per-fixture tests (no separate task)

### Goal-achievement risk: low
- Scope expanded to contribute `:479` (same defect) beyond the literally-named
  `:448` · severity: low · → mitigation: documented above; both covered by the master fixture test

## Verification

```bash
bash tests/test_git_utils.sh
bash tests/test_contribute.sh
bash tests/test_plan_externalize.sh
shellcheck .aitask-scripts/aitask_contribute.sh \
           .aitask-scripts/aitask_plan_externalize.sh \
           .aitask-scripts/lib/git_utils.sh
```

Manual smoke (optional): in a throwaway `master`-default git repo, confirm
`detect_primary_branch` prints `master`.

See **task-workflow Step 9** for post-implementation cleanup, archival, and merge.
