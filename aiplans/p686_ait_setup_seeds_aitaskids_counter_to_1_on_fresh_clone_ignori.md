---
Task: t686_ait_setup_seeds_aitaskids_counter_to_1_on_fresh_clone_ignori.md
Base branch: main
plan_verified: []
---

## Context

`./ait setup` seeds the `aitask-ids` counter branch with `next_id=1` on a fresh
clone of a data-branch-mode repo, even when the `aitask-data` branch already
contains tasks (e.g. up to `t10`). The next `./ait create` then hands out IDs
that collide with existing tasks. (Issue: t686, gh#12.)

**Root cause** — `aitask_setup.sh:main()` calls `setup_id_counter` before
`setup_data_branch`. At that point, on a fresh clone, the local `aitasks/`
directory either does not exist or is just an empty `aitasks/new/` shell
created by `setup_draft_directory`. `aitask_claim_id.sh --init` calls
`scan_max_task_id "aitasks" "aitasks/archived"` (lib/archive_scan.sh:27), which
finds nothing, so it pushes `next_id=1` to `origin/aitask-ids`. By the time
`setup_data_branch` finally creates the `.aitask-data/` worktree and the
`aitasks/` symlink, the counter is already wrong on the remote.

**Fix shape** — Reorder `main()` so `setup_data_branch` runs *before*
`setup_id_counter`. After `setup_data_branch` returns, `aitasks/` is either a
symlink onto a worktree containing the real tasks (data-branch mode) or a
real directory (legacy / declined-prompt mode). Either way,
`scan_max_task_id` then sees the same files `./ait create` will see, so the
counter is initialized correctly.

This is the recommendation from the Phase-1 exploration. Alternative
approaches considered and rejected:

- Adding a `scan_max_task_id_from_ref` helper that reads `origin/aitask-data`
  via `git ls-tree`. More moving parts, doesn't handle tar archives, and
  introduces a parallel scan implementation. The reorder gets the same effect
  for free.
- Removing the early `mkdir -p aitasks/new` in `setup_draft_directory`. Out of
  scope; the reorder fixes the counter bug regardless.

## Files to modify

1. `.aitask-scripts/aitask_setup.sh` — reorder calls in `main()`.
2. `tests/test_data_branch_setup.sh` — add a regression test.

## Implementation steps

### 1. Reorder `main()` in `aitask_setup.sh`

Current order (`.aitask-scripts/aitask_setup.sh:3019–3032`):

```bash
    setup_draft_directory          # creates aitasks/new/
    setup_python_cache_gitignore   # adds entries to .gitignore on main
    setup_id_counter               # scans aitasks/ → seeds aitask-ids   ◄── BUG
    setup_lock_branch              # creates aitask-locks branch
    setup_data_branch              # creates .aitask-data/ + symlinks    ◄── too late
```

New order — move `setup_data_branch` ahead of `setup_id_counter` (and ahead of
`setup_draft_directory`, so the `aitasks/new/` mkdir lands inside the data
branch worktree on fresh data-branch clones rather than as a transient real
dir on main that triggers a no-op migration):

```bash
    setup_data_branch              # NEW position: build aitasks/ first
    setup_draft_directory
    setup_python_cache_gitignore
    setup_id_counter               # now scans the populated aitasks/
    setup_lock_branch
```

Rationale:

- `setup_data_branch` is interactive (Y/n prompt at line 1006). If the user
  declines, it returns without modifying anything, and the rest of `main()`
  proceeds exactly as before. So putting it first is safe in legacy mode.
- `setup_draft_directory`, `setup_python_cache_gitignore`, and
  `setup_lock_branch` do not depend on `setup_data_branch` running first or
  later — the only dependency is `setup_id_counter`'s scan needing
  `aitasks/` to be a stand-in for the real data tree.
- `setup_data_branch`'s migration path (`aitasks/` is a real dir) keeps
  working: in legacy-mode fresh clones (`aitasks/` already on `main`),
  `setup_data_branch` still detects it via `[[ -d aitasks && ! -L aitasks ]]`
  and runs the migration.
- The "fake migration" caused by `setup_draft_directory` creating an empty
  `aitasks/new/` before `setup_data_branch` runs (current behavior) goes
  away. With the new order, `setup_data_branch` runs first against an
  un-touched filesystem, so its needs-migration detection is honest.

No other functions or scripts need changing. `setup_id_counter` already
re-checks `git ls-remote --heads origin aitask-ids` (line 803) and short-
circuits if the counter branch already exists, so it remains idempotent.

### 2. Add regression test in `tests/test_data_branch_setup.sh`

Append a new test (Test 11) just before the summary block at line 474. The
existing helpers (`setup_repo_with_remote`, `assert_eq`, `assert_contains`)
already cover what we need. The test simulates the exact bug scenario and
verifies the counter is initialized to `max+1` rather than `1`.

```bash
# --- Test 11: setup_id_counter respects existing tasks on aitask-data (t686) ---
echo "--- Test 11: counter init with pre-existing tasks on aitask-data ---"

TMPDIR_11="$(setup_repo_with_remote)"

# PC1: set up data branch and seed it with tasks t1, t2, t10
SCRIPT_DIR="$TMPDIR_11/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR" "$TMPDIR_11/local/seed"
cp "$PROJECT_DIR/seed/project_config.yaml" "$TMPDIR_11/local/seed/" 2>/dev/null || true

(cd "$TMPDIR_11/local" && setup_data_branch </dev/null >/dev/null 2>&1)
(
    cd "$TMPDIR_11/local/.aitask-data"
    mkdir -p aitasks
    : > aitasks/t1_alpha.md
    : > aitasks/t2_beta.md
    : > aitasks/t10_gamma.md
    git add aitasks/
    git commit -m "ait: seed tasks" --quiet
    git push --quiet 2>/dev/null
)

# PC2: fresh clone — no aitask-ids branch on remote yet, but aitask-data has t1/t2/t10
git clone --quiet "$TMPDIR_11/remote.git" "$TMPDIR_11/pc2" 2>/dev/null
(cd "$TMPDIR_11/pc2" && git config user.email "test@test.com" && git config user.name "Test")
SCRIPT_DIR="$TMPDIR_11/pc2/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
# The real script lives at PROJECT_DIR; the test repo just needs the dir to
# exist for SCRIPT_DIR-relative resolution by sourced functions.
cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" "$SCRIPT_DIR/"
cp -r "$PROJECT_DIR/.aitask-scripts/lib" "$SCRIPT_DIR/"

# Run setup in the post-fix order: data branch first, THEN counter init.
(cd "$TMPDIR_11/pc2" && setup_data_branch </dev/null >/dev/null 2>&1)
(cd "$TMPDIR_11/pc2" && setup_id_counter </dev/null >/dev/null 2>&1)

# Counter must be max(1,2,10) + 1 = 11, not 1.
counter_val=$(git -C "$TMPDIR_11/pc2" fetch origin aitask-ids --quiet 2>/dev/null \
    && git -C "$TMPDIR_11/pc2" show origin/aitask-ids:next_id.txt 2>/dev/null \
    | tr -d '[:space:]')
assert_eq "Counter seeded to max(existing)+1 on fresh clone" "11" "$counter_val"

rm -rf "$TMPDIR_11"
```

The assertion intentionally exercises the corrected order. The test does
*not* need to cover the buggy order — `bash -n` would still pass on the bug,
and the value of the test is the semantic guarantee, not the code path. If
someone later swaps the calls back, this assertion fails immediately.

## Verification

1. **Existing tests pass after the reorder:**
   ```bash
   bash tests/test_data_branch_setup.sh
   bash tests/test_claim_id.sh
   ```
   Tests 1–10 in `test_data_branch_setup.sh` source the script and call
   individual setup functions directly, so the reorder in `main()` does not
   affect them.

2. **New regression test passes (and would fail pre-fix):**
   ```bash
   bash tests/test_data_branch_setup.sh
   ```
   Look for `Test 11` in the output — `Counter seeded to max(existing)+1 on
   fresh clone` should be PASS.

3. **Lint:**
   ```bash
   shellcheck .aitask-scripts/aitask_setup.sh
   ```
   No new errors.

4. **Manual end-to-end (per CLAUDE.md "Test the full install flow"):**
   In a scratch dir, simulate a fresh-clone scenario by cloning a repo whose
   remote already has an `aitask-data` branch populated with tasks
   t1..t10 and no `aitask-ids` branch. Run `./ait setup` and confirm:

   ```text
   Max existing task ID: t10
   Initializing counter branch with next_id=11 (max + 1)
   Counter branch 'aitask-ids' created with next_id=11
   ```

   Followed by `./ait create` returning `t11` (not `t1`).

5. **Reference Step 9 of task-workflow:** after the implementation is
   approved, the post-implementation cleanup, archival, and merge steps run
   per `.claude/skills/task-workflow/SKILL.md` Step 9.

## Final Implementation Notes

- **Actual work done:** Swapped the call order in `.aitask-scripts/aitask_setup.sh:main()` so `setup_data_branch` runs before `setup_draft_directory`/`setup_python_cache_gitignore`/`setup_id_counter`. Added Test 11 to `tests/test_data_branch_setup.sh` covering the fresh-clone scenario with pre-existing tasks on `aitask-data` (asserts counter = max+1 = 11) plus a static check that asserts `setup_data_branch` precedes `setup_id_counter` inside `main()`. All 51 tests pass; `bash tests/test_claim_id.sh` 23/23 pass.
- **Deviations from plan:** None functional. The plan called for a single new test; I added a second assertion within Test 11 — a grep-based static order check on `main()`'s body — because the in-process unit test calls the helpers in fixed order and would not catch a regression where a future contributor reorders `main()`. The static check ties the test directly to the source-file ordering, which is the real contract.
- **Issues encountered:** `aitask_plan_externalize.sh 686` returned `MULTIPLE_CANDIDATES` because `~/.claude/plans/` had several recent plan files. Resolved by re-running with `--internal /home/ddt/.claude/plans/enumerated-chasing-flurry.md`.
- **Key decisions:**
  - Reorder rather than introduce a `scan_max_task_id_from_ref` helper that reads from `origin/aitask-data` via `git ls-tree`. The reorder is a 4-line change with no new code paths and no parallel scan implementation; the alternative would have duplicated archive-scanning logic and missed tar archives.
  - Move `setup_data_branch` ahead of `setup_draft_directory` (not just ahead of `setup_id_counter`) so the data-branch-mode "fake migration" — where `setup_draft_directory`'s `mkdir -p aitasks/new` made an empty `aitasks/` look like a legacy migration source — no longer happens on fresh data-branch clones.
- **Upstream defects identified:** None. The fix is local to `aitask_setup.sh:main()`'s ordering; no separate pre-existing bug seeded this symptom.
