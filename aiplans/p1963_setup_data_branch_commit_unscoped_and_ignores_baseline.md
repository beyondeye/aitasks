---
Task: t1963_setup_data_branch_commit_unscoped_and_ignores_baseline.md
Base branch: main
Output branch: main
---

# t1963 — Scope `setup_data_branch`'s main-branch commit and honour the dirty baseline

## Context

`setup_data_branch` Step 9 ("Commit on main", `.aitask-scripts/aitask_setup.sh`
~1960-1985) does `git add .gitignore`, a global `git diff --cached --quiet`,
and an **unscoped** `git commit -m …`. Two defects:

1. **Whole-index sweep** — anything another session has staged in this shared
   checkout rides into "ait: Configure task data branch…" /
   "ait: Migrate task data to aitask-data branch".
2. **Ignores `AIT_SETUP_DIRTY_BASELINE`** — a user's pre-setup `.gitignore`
   edit is committed together with the data-branch rules. (t1959 fixed this
   for the six other `.gitignore` helpers via `_ait_commit_gitignore_rule`.)

A plain `-- .gitignore` pathspec is not enough: on the **migration** branch
Step 5 stages `git rm -r aitasks/ aiplans/` and relies on this commit to carry
the removals, and `git commit -- aitasks/…` uses `--only` semantics (reads the
worktree), where `aitasks` is now the symlink into `.aitask-data/`.

**Approach (prototyped in the scratchpad, works):** commit through a *private
index* — `GIT_INDEX_FILE=<tmp>` seeded from HEAD, then apply exactly this
step's own entries (the staged `aitasks/`/`aiplans/` deletions, read by name
from the shared index, and `.gitignore` when it is ours to commit), and
`git commit` that. The shared index keeps any foreign staged work, still
staged; its deletions already match the new HEAD; its `.gitignore` entry is
re-synced to HEAD afterwards.

## Implementation steps

All edits are in `.aitask-scripts/aitask_setup.sh` (plus tests).

1. **Extract the baseline predicate** used by `_ait_commit_gitignore_rule`
   (~line 2291) into a small helper next to it, and make
   `_ait_commit_gitignore_rule` call it (behaviour unchanged):
   ```bash
   # True when .gitignore was dirty (edited, deleted, staged or not) at
   # snapshot_pre_setup_dirty — a setup commit must not carry it (t1959).
   _ait_gitignore_predates_setup() {
       [[ -n "$(printf '%s\n' .gitignore | _ait_intersect "$AIT_SETUP_DIRTY_BASELINE")" ]]
   }
   ```

2. **Add a commit helper** just above `setup_data_branch` (after
   `abort_data_branch_setup`), commented with the why (the `--only`/symlink
   trap, foreign staged work):
   ```bash
   # _ait_commit_data_branch_switch <project_dir> <msg> <with_gitignore> <with_removals>
   _ait_commit_data_branch_switch() {
       local project_dir="$1" msg="$2" with_gitignore="$3" with_removals="$4"
       local tmp_dir rc=0
       tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/ait_setup_index.XXXXXX")" || return 1
       (
           cd "$project_dir" || exit 1
           local idx="$tmp_dir/index"     # mktemp -d: git rejects a 0-byte index file
           if git rev-parse --verify -q HEAD >/dev/null; then
               GIT_INDEX_FILE="$idx" git read-tree HEAD || exit 1
           else
               GIT_INDEX_FILE="$idx" git read-tree --empty || exit 1
           fi
           if [[ "$with_removals" == true ]]; then
               git diff --cached --name-only -z --diff-filter=D -- aitasks aiplans \
                   | GIT_INDEX_FILE="$idx" git update-index -z --force-remove --stdin || exit 1
           fi
           if [[ "$with_gitignore" == true ]]; then
               GIT_INDEX_FILE="$idx" git add -- .gitignore || exit 1
           fi
           GIT_INDEX_FILE="$idx" git diff --cached --quiet && exit 0
           GIT_INDEX_FILE="$idx" git commit -m "$msg" || exit 1
           # Committed. Shared index: the removals already match the new HEAD;
           # resync .gitignore's entry so it does not read as a staged revert.
           if [[ "$with_gitignore" == true ]]; then
               git reset -q -- .gitignore || exit 2
           fi
       ) || rc=$?
       rm -rf "$tmp_dir"
       return "$rc"
   }
   ```
   Return contract: `0` committed (or nothing to commit), `1` the commit
   did not happen, `2` **the commit landed** but the shared-index resync
   failed (e.g. `.git/index.lock` held). Explicit `|| exit N` everywhere: the
   rc is captured with `|| rc=$?`, where errexit is off. Scope is deliberately
   limited to preserving foreign *staged* work — setup is assumed to be the
   only committer while it runs, so no concurrent-commit coordination or
   atomic HEAD-update machinery.

3. **Replace Step 9** in `setup_data_branch` with:
   - `commit_gitignore=false`; if `gitignore_changed == true`: when
     `_ait_gitignore_predates_setup` → `info "  .gitignore had uncommitted
     changes before setup — data-branch rules added but not committed."`,
     else `commit_gitignore=true`. In the dirty case the shared index is not
     touched for `.gitignore` (the old `git add` is gone).
   - Choose the message as today (migrate vs configure) and call
     `_ait_commit_data_branch_switch "$project_dir" "$msg" "$commit_gitignore" "$needs_migration"`.
   - Capture the rc (`… || commit_rc=$?`) and branch:
     - `1` → `warn` that the switch could not be committed on the current
       branch and that the removals stay staged / the `.gitignore` rules stay
       on disk; continue (don't kill setup — the data is already durable on
       the data branch). Today a failing commit aborts all of setup under
       `set -e`.
     - `2` → `warn` that the commit **succeeded** but the index could not be
       updated afterwards, so `.gitignore` may show as a staged revert; `info`
       the reconcile command to run once the index lock clears:
       `git reset -q -- .gitignore`. Continue.
   - Rewrite the Step-9 comment: it is now path-scoped (private index),
     honours the baseline, and why a pathspec commit can't carry the removals.

## Tests — `tests/test_data_branch_setup.sh`, new Test 36 (before the summary)

A `run_data_branch_commit_case <label> <mode: configure|migrate> <gitignore: clean|dirty>`
helper, four cases. Fixture: `setup_local_repo` (configure) /
`setup_migration_fixture` (migrate), plus a tracked `.aitask-scripts/VERSION`
and a committed `.gitignore` (arms the baseline, as Test 34 does); then
`foreign.txt` staged (`git add`); dirty case appends `user-edit-t1963` to
`.gitignore`; then `snapshot_pre_setup_dirty`; `setup_data_branch </dev/null`.
Assertions:
- all cases: `foreign.txt` not in `HEAD`; `git status --porcelain -- foreign.txt`
  is `A  foreign.txt` (still staged, not lost).
- migrate: `git ls-tree HEAD -- aitasks aiplans` empty; HEAD subject is
  "ait: Migrate task data to aitask-data branch"; no staged/unstaged entries
  under `aitasks`/`aiplans` in porcelain.
- clean: `HEAD:.gitignore` contains `.aitask-data`; `.gitignore` porcelain
  empty (index resynced).
- dirty: `HEAD:.gitignore` has neither `user-edit-t1963` nor `.aitask-data`;
  the worktree `.gitignore` has both; porcelain is ` M .gitignore`.
- configure+dirty: HEAD unchanged (no commit at all).
Disarm the baseline afterwards (as after Test 34).

**Test 37 — committed, then the index resync fails.** Configure fixture
(clean `.gitignore`); create `.git/index.lock` before `setup_data_branch`
(the private-index commit locks `<tmp>/index.lock` and the refs, never the
shared index, so the commit lands and only `git reset` hits the lock). If the
configure path turns out to touch the shared index before Step 9, use a
`shim_install git:…` that fails only `git reset` instead. Assert: HEAD
subject is "ait: Configure task data branch…" and `HEAD:.gitignore` has
`.aitask-data`; output contains the "commit succeeded" warning and
`git reset -q -- .gitignore`; output does **not** contain the
"could not commit" warning. Then remove the lock, run the printed command, and
assert `.gitignore` porcelain is empty (the advice actually reconciles).

**Red proof:** run the same scenario against the pre-change function (a copy
of `HEAD:.aitask-scripts/aitask_setup.sh` in the scratchpad, sourced by a
throwaway driver) and confirm the foreign-file and dirty-`.gitignore`
assertions fail there.

## Verification

- `bash tests/test_data_branch_setup.sh` (all, incl. Test 8b/27/28/34)
- `bash tests/test_data_branch_migration.sh`, `bash tests/test_gitignore_data_symlinks.sh`,
  `bash tests/test_setup_git.sh`, `bash tests/test_t644_branch_mode_upgrade.sh`
- `shellcheck .aitask-scripts/aitask_setup.sh`
- Step 9 (Post-Implementation): current-branch mode, no merge; archive via
  `aitask_archive.sh 1963`.

## Risk

### Code-health risk: low
- The private-index commit and the shared index could disagree afterwards (e.g. `.gitignore` showing as a staged revert, or removals re-appearing) · severity: low · → mitigation: none (covered in-plan by the `git reset -- .gitignore` resync and Test 36's porcelain assertions)
- A post-commit index-resync failure could be misreported as "not committed" (inviting a duplicate commit) · severity: low · → mitigation: none (covered in-plan by the distinct rc 2 path and Test 37)
- Changing a commit failure from "setup dies under `set -e`" to "warn and continue" alters failure behaviour on the migration path · severity: low · → mitigation: none (data is already committed on the data branch before Step 9; the removals stay staged for the user)

### Goal-achievement risk: low
None identified.
