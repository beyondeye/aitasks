---
Task: t644_ait_dispatch_not_update_on_upgrade.md
Base branch: main
plan_verified: []
---

# t644: Fix `ait upgrade` not committing framework files in branch-mode setups

## Context

When the user ran `ait upgrade` in `../aitasks_mobile`:
- Framework files **were** extracted by `tar -xzf` (verified: `git diff ait` shows the changes, e.g. `ait install latest` → `ait upgrade latest`).
- Framework files were **not committed** — `git status` lists 14 modified and 14 untracked files (`.aitask-scripts/aitask_upgrade.sh`, `.claude/skills/task-workflow/`, `.claude/skills/ait-git/`, `.claude/skills/user-file-select/`, etc.) all left dangling.
- The latest commit on `master` is still `851bd35 ait: Add aitask framework` (pre-upgrade) — confirming `commit_installed_files()` produced no commit.

### Root cause

`install.sh::commit_installed_files()` (lines 686–752) calls:

```bash
git add "${paths_to_add[@]}" 2>/dev/null || true
```

In branch-mode setups, `aitasks/` is a symlink to `.aitask-data/aitasks/` (separate worktree). `git add aitasks/metadata/` fails with:

```
fatal: pathspec 'aitasks/metadata/' is beyond a symbolic link
```

(exit 128 — confirmed empirically in `aitasks_mobile`). `git add` is atomic across pathspecs: a single fatal pathspec aborts the whole command, so **none** of the other paths (`.aitask-scripts/`, `ait`, `.claude/skills/`, …) get staged. The `2>/dev/null || true` swallows the error silently.

Worse, the subshell:

```bash
) && success "Framework update committed to git" \
  || warn "Could not commit framework update (non-fatal)."
```

still exits 0 because `git diff --cached --quiet` finds nothing staged and the `git commit` line is skipped — so the script falsely reports "Framework update committed to git" when nothing was committed.

`aitask_setup.sh::commit_framework_files()` (lines 2393–2538) does **not** have this bug because it first discovers actual changed files via `git ls-files --others --exclude-standard` and `git ls-files --modified` (which silently skip paths beyond symlinks), then runs `git add -- "${changed_files[@]}"` on individual files. We will mirror that pattern in install.sh.

### Secondary concern: data-branch files are also un-committed

`install_seed_*` functions (profiles, project_config, models, codex/opencode/gemini staging) write through the `aitasks/metadata/` symlink into the `.aitask-data` worktree. Those changes belong on the `aitask-data` branch and need a separate commit there. install.sh currently makes no attempt to commit them.

### Stale "install" wording in `ait --help`

The `ait` file *is* updated by `tar -xzf` and the `case` dispatch correctly routes `upgrade` (line 160). But `show_usage()` (line 75) still advertises the old verb:

```
  install        Update aitasks to latest or specific version
```

There is no `install` case in the dispatcher — only `upgrade`. The help text is a leftover from the t641 rename. The user observed this and (reasonably) inferred the file wasn't updated. Fix the wording to match the dispatch.

## Changes

### 1. Fix `install.sh::commit_installed_files()` (single-file change)

**File:** `install.sh` (lines 686–752)

Replace the bulk `git add "${paths_to_add[@]}"` with the discover-then-add pattern used by `aitask_setup.sh::commit_framework_files()`. New flow:

1. Bail-outs unchanged (`rev-parse --is-inside-work-tree`, `ls-files --error-unmatch .aitask-scripts/VERSION`).
2. Build `paths_to_add` list unchanged.
3. **Discover** changed files (mirroring setup.sh):
   ```bash
   local cache_artifacts_re='(^|/)__pycache__/|\.py[co]$|\.pyd$'
   untracked="$(cd "$INSTALL_DIR" && git ls-files --others --exclude-standard \
       "${paths_to_add[@]}" 2>/dev/null | grep -Ev "$cache_artifacts_re")" || true
   modified="$(cd "$INSTALL_DIR" && git ls-files --modified \
       "${paths_to_add[@]}" 2>/dev/null | grep -Ev "$cache_artifacts_re")" || true
   all_changes="$(printf '%s\n%s\n' "$untracked" "$modified" | sed '/^$/d')"
   ```
   `git ls-files` silently skips paths beyond symlinks, so `aitasks/metadata/` drops out of the result on branch-mode setups without erroring.
4. If `all_changes` is empty, log "All framework files already committed" and return.
5. **Stage** the discovered files individually, capturing stderr so failures surface:
   ```bash
   if ! add_output=$(cd "$INSTALL_DIR" && git add -- "${changed_files[@]}" 2>&1); then
       warn "git add failed:"
       printf '%s\n' "$add_output" | awk '{print "    " $0}'
       warn "Framework files NOT committed."
       return
   fi
   ```
6. **Commit** if anything is staged:
   ```bash
   if ! (cd "$INSTALL_DIR" && git diff --cached --quiet 2>/dev/null); then
       if ! commit_output=$(cd "$INSTALL_DIR" && \
           git commit -m "ait: Update aitasks framework to v${version}" 2>&1); then
           warn "git commit failed:"
           printf '%s\n' "$commit_output" | awk '{print "    " $0}'
           return
       fi
       success "Framework update v${version} committed to git ($total_count files)"
   fi
   ```
7. **Post-commit verification** (mirroring setup.sh): re-run `ls-files --others --exclude-standard` and warn if any framework files remain untracked. This is the diagnostic the user asked for ("can you check if ait upgrade actually worked").
8. Keep the existing one-time `__pycache__` cleanup (lines 742–746) before the commit.
9. Drop the misleading `&& success "..." || warn "..."` outer construct — replace with explicit success/warn calls inside each branch.

### 2. Commit data-branch changes when `.aitask-data` worktree exists

**Same file:** add a new helper `commit_installed_data_files()` invoked right after `commit_installed_files()` in `main()`.

Logic (replicating `task_utils.sh::_ait_detect_data_worktree` inline — install.sh runs stand-alone via `curl|bash` and cannot source helpers):

```bash
commit_installed_data_files() {
    local data_dir="$INSTALL_DIR/.aitask-data"
    [[ -d "$data_dir/.git" || -f "$data_dir/.git" ]] || return  # legacy mode → nothing to do

    if ! git -C "$data_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        return
    fi

    # Only commit metadata/ — task/plan content is user data, not framework
    local data_paths=("aitasks/metadata/" "aireviewguides/")
    local existing_paths=()
    for p in "${data_paths[@]}"; do
        [[ -e "$data_dir/$p" ]] && existing_paths+=("$p")
    done
    [[ ${#existing_paths[@]} -gt 0 ]] || return

    # Discover changed files inside the data worktree (same pattern as #1)
    untracked=...; modified=...; all_changes=...
    [[ -z "$all_changes" ]] && return

    git -C "$data_dir" add -- "${changed_files[@]}"
    if ! git -C "$data_dir" diff --cached --quiet 2>/dev/null; then
        git -C "$data_dir" commit -m "ait: Update aitasks framework data to v${version}"
        success "Framework data update v${version} committed to aitask-data branch"
    fi
}
```

Note: only `aitasks/metadata/` and `aireviewguides/` (when symlinked) are committed — never task or plan content. Both are framework-owned config dirs.

Wire-up in `main()` (after `commit_installed_files`):
```bash
commit_installed_files
commit_installed_data_files
```

### 3. Fix stale help text in `ait`

**File:** `ait` line 75 (inside `show_usage()`).

Replace:
```
  install        Update aitasks to latest or specific version
```
with:
```
  upgrade        Update aitasks to latest or specific version
```

No other dispatcher changes needed — `upgrade` is already wired (line 160) and there is no `install` case to remove.

### 4. Mirror the same hardening in `aitask_setup.sh::commit_framework_files()` for parity

`commit_framework_files()` already uses the discover-then-add pattern correctly (no symlink bug). But it does **not** commit data-branch changes. Add a parallel `commit_framework_data_files()` helper invoked at the end of setup. This is a setup-time analogue of the install.sh #2 helper. Since setup.sh *can* source `task_utils.sh`, prefer using `task_git` (or replicate inline if sourcing is awkward at this point in setup.sh).

This keeps `ait setup` and `ait upgrade` symmetric: both commit master-branch framework files and (if branch mode) data-branch metadata files.

## Files to modify

1. `install.sh` — `commit_installed_files()` rewrite + new `commit_installed_data_files()`; `main()` wiring.
2. `ait` line 75 — `install` → `upgrade` in the help text.
3. `.aitask-scripts/aitask_setup.sh` — new `commit_framework_data_files()`; called from `main()` immediately after the existing `commit_framework_files`.
4. `tests/` — add a minimal regression test (see Verification).

## Reference files (existing patterns to reuse)

- `aitask_setup.sh:2393–2538` — `commit_framework_files()`: the discover-then-add pattern to mirror in install.sh, including the `cache_artifacts_re` filter, post-commit verification, and explicit error capture.
- `.aitask-scripts/lib/task_utils.sh:23–172` — data-worktree detection (`_ait_detect_data_worktree`) and `task_git()` wrapper. Inline-replicate the `[[ -d "$data_dir/.git" || -f "$data_dir/.git" ]]` check in install.sh.
- `tests/test_t167_integration.sh` — integration test pattern for the original `commit_installed_files()` work (t167); the new branch-mode regression test should follow this style.

## Verification

### Manual reproduction (before fix)

In a branch-mode project (e.g. `aitasks_mobile`):
```bash
git status --porcelain   # expect: M ait + many ?? new files (current state)
git log --oneline -1     # expect: still on pre-upgrade commit
```

### Manual verification (after fix)

Run a fresh upgrade in a clean branch-mode test project:
```bash
ait upgrade latest
```
Expected:
- `[ait] Framework update v0.X.Y committed to git (N files)` — N matches actual count.
- `git log --oneline -1` shows `ait: Update aitasks framework to v0.X.Y`.
- `git status` is clean for framework paths (any leftover surfaces via post-commit warning).
- If branch-mode: a second commit `ait: Update aitasks framework data to v0.X.Y` appears on the `aitask-data` branch (`./ait git log -1`).

### Automated test

Add `tests/test_t644_branch_mode_upgrade.sh`:
1. Set up a temp git repo with the symlink+`.aitask-data` layout.
2. Stage a fake "old" install with `.aitask-scripts/VERSION` tracked.
3. Re-run a relevant slice of `commit_installed_files()` (or invoke install.sh with `--local-tarball` against a synthetic newer tarball).
4. Assert: a commit exists on the master branch covering `.aitask-scripts/`, `ait`, `.claude/skills/`; and (if data worktree present) a commit exists on `aitask-data` covering `aitasks/metadata/`.
5. Assert: `git status --porcelain` for framework paths is empty.

### Existing tests

Run `bash tests/test_t167_integration.sh` to confirm no regression on the legacy (non-branch) path.

## Non-goals

- **Propagating to `.agents/`, `.codex/`, `.gemini/`, `.opencode/` during upgrade.** These are populated by `setup_codex_cli` / `setup_gemini_cli` / `setup_opencode` in `aitask_setup.sh` from staging dirs in `aitasks/metadata/`. Keeping `ait setup` as the propagation step is intentional (each agent's setup is interactive — installs settings/permissions, edits CLI configs). After this fix, `ait upgrade` followed by `ait setup` remains the documented path; no scope creep into install.sh. If the user later wants `ait upgrade` to invoke a non-interactive subset of setup, that is a separate task.
- **Tracking the `aitasks` / `aiplans` symlinks themselves on master.** In `aitasks_mobile` they show as `?? aitasks` `?? aiplans` — pre-existing; t644 is scoped to the commit-after-upgrade bug.

## Post-implementation step (Step 9)

Standard archival — see SKILL.md Step 9: commit code + plan separately, run `verify_build` if configured (none in this project), no worktree to clean (profile = `fast` / `create_worktree: false`).

## Final Implementation Notes

- **Actual work done:**
  - `install.sh::commit_installed_files()` rewritten in the discover-then-add style of `aitask_setup.sh::commit_framework_files()`: `git ls-files --others/--modified` first, then `git add -- <files>` on individual paths (avoids the symlink atomicity bug).
  - New `install.sh::commit_installed_data_files()` — when `.aitask-data/.git` exists, commits `aitasks/metadata/` and `aireviewguides/` (if present) on the `aitask-data` branch.
  - New `aitask_setup.sh::commit_framework_data_files()` — interactive analogue of the install.sh helper, wired in `main()` after `commit_framework_files`.
  - `ait` line 75: `install` → `upgrade` in the Infrastructure section of `show_usage()`.
  - `tests/test_t644_branch_mode_upgrade.sh` — 16 assertions, three scenarios (branch-mode upgrade, idempotent re-run, legacy mode unchanged).
- **Deviations from plan:**
  - **Conditional data-branch filter, not unconditional.** The plan called for an `^(aitasks|aiplans)/` filter on `git ls-files` output. Initial implementation made it unconditional, which broke `test_setup_git.sh` Test 2's "aitasks/metadata/ committed" assertion in legacy mode (where `aitasks/metadata/` legitimately lives on the main branch). Fixed by gating the filter on `[[ -d .aitask-data/.git || -f .aitask-data/.git ]]` and refactoring it into a small `_filter_changes` helper used in three places per file. Same conditional filter mirrored in `aitask_setup.sh`.
  - **Pre-existing test failures fixed in scope.** User asked us to investigate the "unrelated" failures we initially flagged. They turned out to be stale assertions: `test_setup_git.sh` line 132 expected the pre-t624 message `"not yet committed"` (renamed to `"READY TO COMMIT N FRAMEWORK FILES"` by t624); `test_t167_integration.sh` Scenarios A and D expected install.sh to auto-commit on first install, which t637 deliberately stopped (sentinel-skip when `.aitask-scripts/VERSION` not yet tracked). Updated both: t167 Scenario A now asserts the correct sentinel-skip + ait setup commit flow; Scenario D now exercises the upgrade-commit path with a bumped tarball. After fixes: t167 17/17, setup_git 38/38.
- **Issues encountered:**
  - First test attempt failed because `git ls-files --others --exclude-standard "aitasks/metadata/"` does *not* always silently skip paths beyond the `aitasks` symlink: when the symlink target lives inside the worktree (`.aitask-data/` is a sibling of `aitasks` symlink under `INSTALL_DIR`) AND the symlink is tracked, ls-files walks through it and returns paths from the data worktree. Hence the filter had to be defensive, not a "should never trigger" theoretical safety.
  - Initial test setup used per-path `git add` flags (`git add .aitask-scripts/ ait .claude/`, then `git add -A aireviewguides/ ...`); switching to a single `git add -A` removed an unreliable code path.
  - `git add` of an existing tarball-extracted symlink target sometimes follows the symlink for the staged hunks; this is what the conditional filter compensates for.
- **Key decisions:**
  - **Stand-alone `commit_installed_data_files()` rather than sourcing `task_utils.sh`.** install.sh is downloaded by `curl|bash` and runs before the framework is extracted, so it cannot rely on `.aitask-scripts/lib/task_utils.sh`. Inline-replicating `_ait_detect_data_worktree`'s `[[ -d .git || -f .git ]]` test is acceptable duplication (single function, well-commented).
  - **Data branch helper restricted to `aitasks/metadata/` + `aireviewguides/`.** Never commits task or plan content to the data branch automatically — those are user data, not framework. Keeps the two helpers narrow and predictable.
  - **Two pre-existing test failures fixed inline.** They blocked the ability to verify "no regression"; leaving them in place would have meant every future change was 5 failures away from "tests pass". Re-aligning them was a small scoped cleanup, not feature creep.
- **Build verification:** No `verify_build` configured in `aitasks/metadata/project_config.yaml` — skipped per Step 9 rules.
