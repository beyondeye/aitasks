---
Task: t1972_setup_dirty_baseline_data_gate_and_staged_renames.md
Base branch: main
Output branch: main
---

# t1972 — setup dirty baseline: data gate + staged renames

## Context

t1964 gave `install.sh` (`ait upgrade`) a pre-install dirty baseline in which
each baseline is gated on exactly its own committer's eligibility predicate and
the staged term uses `--no-renames`. Plan review found that the model it was
copied from — `aitask_setup.sh` — has two holes:

1. **Data baseline hidden behind the main bootstrap guard.**
   `snapshot_pre_setup_dirty` (`.aitask-scripts/aitask_setup.sh:4257`) returns
   early when the main repo is not a work tree, has no HEAD, or has
   `.aitask-scripts/VERSION` untracked — before it reaches the `.aitask-data`
   baseline. `commit_framework_data_files` has no main-repo guard at all, so a
   dirty `aitasks/metadata/` edit on the data branch is swept into
   `ait: Add aitask framework data`.
   In miniature the main baseline has the same mismatch: `commit_framework_files`
   needs no HEAD, so a HEAD-less repo with a staged VERSION commits against an
   empty baseline (a user's staged `.gitignore` gets swept).
2. **Staged renames.** `_ait_list_framework_changes` (`:4207`) runs
   `git diff --cached --name-only` with rename detection on, which lists only the
   destination. The source has left the index, so `ls-files --modified` can't
   recover it either. When a setup step recreates the source, it gets committed,
   which turns the user's pending rename into an addition.

Outcome: each setup baseline is captured whenever its committer can act, and a
staged rename is baselined on both sides. Reference: `install.sh:1218-1326`
(`_install_commit_eligible`, `_install_data_worktree_present`,
`_install_list_changes`, `snapshot_pre_install_dirty`).

## Implementation

### 1. `.aitask-scripts/aitask_setup.sh` — `_ait_list_framework_changes`

Add `--no-renames` to the staged term:

```bash
staged="$(git -C "$workdir" diff --cached --name-only --no-renames -- "$@" 2>/dev/null)" || true
```

Extend the function's header comment with the reason. Mirror the install.sh
wording: with rename detection a staged rename lists only its destination; the
source is invisible to `ls-files --modified` too; a recreated source would turn
the pending rename into an addition. `install.sh:1266` already says it "Mirrors
_ait_list_framework_changes", and after this change that claim is true.

### 2. `_ait_data_framework_paths` — add `include_absent`

Give it the same optional second argument `include_absent` that
`_ait_framework_paths` has, defaulting to 0 so the committer's call stays
existence-filtered. This brings it level with install.sh's
`_install_data_framework_paths "$data_dir" 1`. Reason: a fully deleted (staged
or unstaged) `aireviewguides/` on the data branch is a pre-existing change, the
same t1959 rule the main baseline already follows.

### 3. `snapshot_pre_setup_dirty` — reorder and regate

```bash
snapshot_pre_setup_dirty() {
    local project_dir="$SCRIPT_DIR/.."
    local data_dir="$project_dir/.aitask-data"
    local p
    AIT_SETUP_BASELINE_ARMED=1
    AIT_SETUP_DIRTY_BASELINE=""
    AIT_SETUP_DATA_DIRTY_BASELINE=""

    # Data baseline — gated only on commit_framework_data_files' own predicate
    # (data worktree present), independent of the main repo's state: the data
    # committer has no main-repo guard.
    if [[ -d "$data_dir/.git" || -f "$data_dir/.git" ]] && \
       git -C "$data_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        local data_paths=()
        while IFS= read -r p; do data_paths+=("$p"); done < <(_ait_data_framework_paths "$data_dir" 1)
        AIT_SETUP_DATA_DIRTY_BASELINE="$(_ait_list_framework_changes "$data_dir" "" \
            "${data_paths[@]}")" || true
    fi

    # Main baseline — work tree + VERSION in the index. No HEAD requirement:
    # commit_framework_files reads the index, so a repo with no first commit
    # and a staged VERSION is not a bootstrap.
    if ! git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null || \
       ! git -C "$project_dir" ls-files --error-unmatch -- .aitask-scripts/VERSION &>/dev/null; then
        return 0
    fi
    ... (main fw_paths capture unchanged)
}
```

- The bootstrap trade-off (VERSION untracked → empty main baseline →
  commit-all) is **kept**. `commit_framework_files` is deliberately the
  first-time tracker of a fresh install, so the main gate cannot be simply
  "work tree": that would baseline every extracted file and setup would then
  commit nothing. Rewrite the function's header comment to say this. Each
  baseline is gated on its own committer; the main gate is "VERSION in the
  index" (HEAD no longer required); the data baseline is independent of the
  main repo.
- With `include_absent=1` the data path list is never empty, so the
  `${#data_paths[@]} -gt 0` guard goes away. This is the same shape as
  install.sh.
- `aidocs/framework/failopen_git_probes.md` A9/A9b cite stale line numbers. The
  owning task is t1747_4, and this change does not alter the probes' fail-open
  semantics, so that doc is left untouched.

### 4. `tests/test_setup_git.sh` — Test 28 (three shapes + the include-absent sub-shape)

Add the block before the final disarm/summary. Use the existing
`setup_fake_project` and the `assert_*` helpers, and disarm after each case
(`AIT_SETUP_BASELINE_ARMED=0`, as Tests 20–23 do).

- **28a — data baseline with VERSION untracked:** main repo = `setup_fake_project`
  plus `git init` and a commit of `readme.txt` only, so VERSION stays untracked.
  Create a standalone `.aitask-data` repo the way Test 23 does, with a tracked
  `aitasks/metadata/tracked.txt`. Append an edit to `tracked.txt`, run the
  snapshot, then write `aitasks/metadata/new_config.yaml` and run
  `commit_framework_data_files`.
  Assert: the data HEAD commit carries `new_config.yaml` and not `tracked.txt`;
  `tracked.txt` is still ` M`; and `tracked.txt` is in
  `AIT_SETUP_DATA_DIRTY_BASELINE`.
- **28a2 — data dir deletion (include_absent):** in the same kind of data repo,
  track `aireviewguides/g.md`, then `git rm -r -q aireviewguides`. Run the
  snapshot, recreate `aireviewguides/g.md`, and run `commit_framework_data_files`.
  Assert: no commit carries `aireviewguides/g.md` (HEAD count unchanged or HEAD
  lacks the path), and the staged `D aireviewguides/g.md` is still staged.
- **28b — HEAD-less + staged VERSION + staged `.gitignore`:** run
  `setup_fake_project` and `git init`, with no commit. `git add` VERSION. Write
  `.gitignore` = `user-rule.log` and `git add` it. Run the snapshot. Simulate
  setup by appending `aiwork/` to `.gitignore` on disk and writing
  `aireviewguides/x.md`, then run `commit_framework_files`.
  Assert: HEAD exists and its commit carries `aireviewguides/x.md` but not
  `.gitignore`; the index `.gitignore` (`git show :.gitignore`) still reads
  `user-rule.log` without `aiwork/`; the output says "left alone".
- **28c — staged rename:** run `setup_fake_project`, `git init`, `git add -A`
  and commit, so VERSION is tracked. Run **`git -C "$d" config diff.renames true`**.
  The test inherits the developer's git config: there is no `GIT_CONFIG_GLOBAL`
  or `GIT_CONFIG_NOSYSTEM` isolation. Under an inherited `diff.renames=false`,
  the pre-fix `diff --cached --name-only` already lists both sides, so 28c
  would pass vacuously and lose its negative control. A repo-local value
  overrides global and system config. Then `git mv .aitask-scripts/placeholder.sh
  .aitask-scripts/renamed.sh`. Run the snapshot. Recreate
  `.aitask-scripts/placeholder.sh`, write `.aitask-scripts/newly_installed.sh`,
  and run `commit_framework_files`.
  Assert: the HEAD commit carries `newly_installed.sh` and neither
  `placeholder.sh` nor `renamed.sh`;
  `git diff --cached --name-status --no-renames` still shows
  `D<TAB>.aitask-scripts/placeholder.sh` and `A<TAB>.aitask-scripts/renamed.sh`.

**Negative control (red proof):** before editing `aitask_setup.sh`, run the new
Test 28 against the unmodified function and confirm that 28a, 28b and 28c fail.
For 28a2, the pre-fix behaviour is masked because the VERSION guard returns
early in 28a's state. 28a2 uses a tracked VERSION, so pre-fix it fails only
because of the missing `include_absent`. Record which assertions went red.
Do **not** use `git stash` to get the baseline (memory rule). Instead, add the
test first, run it, then apply the fix.

## Verification

- `bash tests/test_setup_git.sh` — everything passes, including the new Test 28
  (and Tests 20–27 still pass, which guards the bootstrap and t1959 behaviour).
- Red proof as described above (new cases fail before the source edit).
- Related suites: `bash tests/test_data_branch_setup.sh`,
  `bash tests/test_upgrade_prunes_retired_scripts.sh`,
  `bash tests/test_install_upgrade_dirty_baseline.sh`.
- `shellcheck .aitask-scripts/aitask_setup.sh`

## Step 9 (Post-Implementation)

Current-branch workflow: commit the code (`bug: … (t1972)`) with explicit
pathspecs only (the worktree has unrelated concurrent dirt). Commit the plan via
`aitask_task_commit.sh`, then archive per Step 9.

## Risk

### Code-health risk: low
None identified. The change is confined to one function's ordering and gating,
one flag, and one optional parameter. It mirrors the already-reviewed install.sh
implementation, and the existing Tests 20–27 pin the bootstrap and deletion
behaviour that must not regress.

### Goal-achievement risk: low
None identified. All three defect shapes named in the task get a direct
regression case that is proven red before the fix. `git diff --cached` on an
unborn HEAD listing staged paths is already exercised by install's G2b.

## Final Implementation Notes
- **Actual work done:** `aitask_setup.sh` — `snapshot_pre_setup_dirty` now captures the data baseline first, gated only on the data-worktree-present predicate `commit_framework_data_files` uses, then the main baseline gated on work tree + VERSION in the index (HEAD requirement dropped); bootstrap commit-all kept for VERSION-not-in-index. `_ait_list_framework_changes` adds `--no-renames` to its staged term. `_ait_data_framework_paths` gained an optional `include_absent` arg (default 0, committer unchanged); the snapshot passes 1, so the `${#data_paths[@]} -gt 0` guard went away. Header comments rewritten. `tests/test_setup_git.sh` Test 28 adds cases 28a / 28a2 / 28b / 28c.
- **Deviations from plan:** None. Post-plan-review change before approval: 28c pins `git config diff.renames true` repo-locally (an inherited `diff.renames=false` would make the pre-fix staged query list both sides and void the negative control).
- **Issues encountered:** None. Red proof: with Test 28 added and the source unmodified, 10 assertions failed across all four cases (28a ×3, 28a2 ×2, 28b ×3, 28c ×2); 146 others passed. After the fix: 156/156. Related suites `test_data_branch_setup.sh` (291/291), `test_upgrade_prunes_retired_scripts.sh`, `test_install_upgrade_dirty_baseline.sh` exit 0. shellcheck: only pre-existing findings, none on changed lines.
- **Key decisions:** The main gate is NOT "work tree only" even though `commit_framework_files` has no VERSION guard: its role as the first-time tracker of a fresh install needs the empty-baseline bootstrap, otherwise every extracted file would be baselined and nothing committed. `git commit -- <paths>` on an unborn HEAD with other paths staged (28b) works and leaves the user's staged `.gitignore`/VERSION in the index.
- **Upstream defects identified:** None
