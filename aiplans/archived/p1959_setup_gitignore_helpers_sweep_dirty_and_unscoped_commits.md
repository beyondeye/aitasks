---
Task: t1959_setup_gitignore_helpers_sweep_dirty_and_unscoped_commits.md
Base branch: main
Output branch: main
---

# t1959 — `.gitignore` setup helpers: no index sweeps, honour the dirty baseline

## Context

Six `ait setup` helpers add one ignore rule each and then commit `.gitignore`
themselves: `setup_draft_directory`, `setup_python_cache_gitignore`,
`setup_gate_logs_gitignore`, `setup_testmap_gitignore`,
`setup_shadow_store_gitignore`, `setup_worktree_dirs_gitignore`
(`.aitask-scripts/aitask_setup.sh` ~2283–2850). They have two defects:

1. **Whole-index sweep.** Five of them run `git add .gitignore && git commit -m …`
   with no pathspec, so anything a concurrent session has staged in the shared
   checkout goes into the setup commit. Only `setup_testmap_gitignore` passes
   `-- .gitignore`.
2. **They ignore `AIT_SETUP_DIRTY_BASELINE`.** `snapshot_pre_setup_dirty` records
   which framework paths were already dirty before setup ran, and
   `commit_framework_files` subtracts that set. The helpers skip this check. When
   their rule is missing, a user's uncommitted `.gitignore` edit goes into the
   helper's commit.

t1711 worked around this only for its own repair, by running
`setup_data_gitignore_symlink_safe` last, just before `commit_framework_files`.
This task fixes the helpers themselves.

## Approach

Each helper keeps its own commit, so the separate, descriptive commit messages
stay. All six route that commit through one new function, which:

- commits path-scoped (`git add -- .gitignore` and `git commit … -- .gitignore`).
  The `--only` semantics of a pathspec commit leave other staged entries alone.
- does **not** commit when `.gitignore` is in `AIT_SETUP_DIRTY_BASELINE`. The rule
  stays on disk, where it takes effect anyway, and setup prints a note.
  `commit_framework_files` already reports a baselined `.gitignore` under
  "Pre-existing uncommitted changes … left alone". This matches the baseline
  contract: "if setup rewrites a file that was already dirty, that file's update
  goes uncommitted rather than sweeping the developer's edit."

When the baseline is unarmed or empty (direct test calls, or the bootstrap case
on a fresh install), nothing is skipped. That keeps the existing
helper-commits-its-rule tests valid (test_setup_git Test 18, test_t167,
test_install_engine_binary G).

Membership uses the existing `_ait_intersect`, so "is `.gitignore` dirty-at-baseline"
means exactly what `commit_framework_files` means by it.

## Steps

### 0. Baseline capture must see deletions (review finding: dirty-baseline deletion)

`_ait_framework_paths` (`aitask_setup.sh` ~4085) prints a path only when
`[[ -e "$project_dir/$p" ]]`, and `snapshot_pre_setup_dirty` scans only that
list. So when a tracked `.gitignore` has been deleted before setup, with the
deletion unstaged (`rm`) or staged (`git rm`), it is never scanned and never
lands in the baseline. A helper then recreates the file and, under the gate
from Step 1, commits it. That overrides the user's deletion. The same gap
affects every deleted tracked framework path when `commit_framework_files`
recreates it.

Fix it in the capture, not in the helper:

- Give `_ait_framework_paths` an optional second argument, `include_absent`.
  When it is `1`, the function prints every entry of `check_paths` and of the
  `install.sh`/CI list without the existence test. The default (no argument)
  is unchanged, because `commit_framework_files` still needs only paths that
  exist (`git add` of an untracked pathspec that does not exist errors out).
- `snapshot_pre_setup_dirty` calls `_ait_framework_paths "$project_dir" 1`.
  `git ls-files --others/--modified` and `git diff --cached --name-only` accept
  pathspecs with no match and print nothing, so the unfiltered list is safe.
  For a deleted tracked file they print exactly the deletion: `ls-files -m`
  covers an unstaged deletion, `diff --cached` a staged one.
- Update the comment above `snapshot_pre_setup_dirty`/`_ait_framework_paths`
  to say why the snapshot scans absent paths (a deletion is a pre-existing
  change).

Downstream this needs no further change. The helper (Step 1) finds `.gitignore`
in the baseline and skips. Later, `commit_framework_files` lists the recreated
`.gitignore` (modified, or untracked after a staged deletion), finds it in the
baseline, and reports it as left alone.

### 1. `.aitask-scripts/aitask_setup.sh` — the shared commit function

Add it just before `setup_draft_directory` (next to the "Draft directory and
gitignore setup" banner):

```bash
# --- Commit a rule a .gitignore helper just appended (t1959) ---
# Path-scoped: a bare `git commit` would carry whatever another session staged
# in this shared checkout. And never over a pre-setup edit: when .gitignore was
# already dirty at snapshot_pre_setup_dirty, committing it would put the user's
# uncommitted change into a setup commit, so the rule stays on disk
# (effective, uncommitted) and commit_framework_files reports the file as
# left alone. An unarmed/empty baseline (direct calls, fresh install) commits.
_ait_commit_gitignore_rule() {
    local project_dir="$1" msg="$2"
    git -C "$project_dir" rev-parse --is-inside-work-tree &>/dev/null || return 0
    if [[ -n "$(printf '%s\n' .gitignore | _ait_intersect "$AIT_SETUP_DIRTY_BASELINE")" ]]; then
        info "  .gitignore had uncommitted changes before setup — rule added but not committed."
        return 0
    fi
    (cd "$project_dir" && git add -- .gitignore && git commit -m "$msg" -- .gitignore 2>/dev/null) || true
}
```

(`_ait_intersect` and `AIT_SETUP_DIRTY_BASELINE` are defined further down the
file. Bash resolves both at call time, and every caller runs from `main()` or a
sourced test after the whole file is loaded.)

### 2. Route all six helpers through it

In each helper, replace the
`if git -C … rev-parse …; then (cd … && git add .gitignore && git commit …) || true; fi`
block with:

```bash
_ait_commit_gitignore_rule "$project_dir" "ait: Add <rule> to .gitignore (<why>)"
```

Each helper keeps its current message verbatim. Drop the now-stale sentence in
the `setup_testmap_gitignore` header comment ("Unlike the older helpers above,
the commit names its one path…"), since every helper now does that.

### 3. Refresh the t1711 rationale comments (same file)

- The `setup_data_gitignore_symlink_safe` header comment and the `main()` comment
  above its call both say the earlier helpers "self-commit without the
  baseline". Reword them. The repair still runs last, because a helper's
  clean-baseline commit placed after it would carry the repair under that
  helper's message. The baseline itself is now honoured everywhere.
- `tests/test_data_branch_setup.sh` Test 35 (placement pin) stays as it is. Only
  its comment needs to follow the new rationale, if it restates the old one.

### 4. Tests

**`tests/test_data_branch_setup.sh` Test 34**. Its dirty-case precondition
("the earlier helper self-committed its rule") is the defect being fixed, so
case `a` changes to:
- HEAD's `.gitignore` has **neither** `.aitask-testmap/` **nor** the repair
  (the legacy `.aitask-data/` line is still there) and lacks `user-edit-t1711`;
- on disk: the testmap rule, the repair and the user edit are all present;
  `status --porcelain -- .gitignore` = `M .gitignore`.

Case `b` (clean) keeps its current assertions. Update the test's header comment.

**New test in `tests/test_setup_git.sh`, table-driven over all six helpers**
(this file already covers the helper commits, in Tests 7/18). For each
`(helper, rule)` pair, build a fresh `setup_fake_project` repo with a committed
`.gitignore` that lacks the rule and a tracked `.aitask-scripts/VERSION` (which
arms a real baseline):

- **(a) dirty baseline.** Append `user-edit` to `.gitignore`, run
  `snapshot_pre_setup_dirty`, then the helper. Assert: HEAD commit count
  unchanged; HEAD `.gitignore` contains neither the rule nor `user-edit`; on disk
  it contains both.
- **(b) foreign staged file, clean `.gitignore`.** Stage an unrelated
  `foreign.txt`, run `snapshot_pre_setup_dirty`, then the helper. Assert: exactly
  one new commit, whose `--name-only` is just `.gitignore`; HEAD `.gitignore`
  has the rule; `foreign.txt` is still staged (`diff --cached --name-only`)
  and absent from HEAD.

- **(c) unstaged deletion.** `rm .gitignore` (tracked), run
  `snapshot_pre_setup_dirty`, then the helper. Assert: `.gitignore` is in
  `AIT_SETUP_DIRTY_BASELINE`; no new commit; HEAD `.gitignore` is the original
  content; the recreated file (rule only) is on disk and
  `status --porcelain -- .gitignore` reads ` M .gitignore`.
- **(d) staged deletion.** `git rm -q .gitignore`, run the snapshot, then the
  helper. Assert: in the baseline; no new commit; HEAD `.gitignore` unchanged;
  the staged deletion is still in the index (`git diff --cached --name-status
  -- .gitignore` = `D`).

Run (c) and (d) on one representative helper (`setup_python_cache_gitignore`)
rather than all six. The defect sits in the shared capture, not in a helper.

- **(e) commit_framework_files over a deleted framework file.** In a repo with
  tracked VERSION and `CLAUDE.md`, `rm CLAUDE.md`, snapshot, recreate
  `CLAUDE.md` with different content, then run `commit_framework_files </dev/null`.
  Assert: `CLAUDE.md` is not in HEAD's last commit, HEAD keeps the original
  content, and the output contains "left alone". This pins the generalized
  capture for a path other than `.gitignore`.

After the block, disarm the baseline (`AIT_SETUP_BASELINE_ARMED=0`, both baselines
empty), as Test 34 does. Keep bodies at top level (no `( … )` around asserts),
as the file does today, so the in-process counters stay valid.

**Red proof (negative control).** Run the new block and the updated Test 34
against the **pre-fix** `aitask_setup.sh`. Use a scratch `git worktree add` of
`HEAD` under the session scratchpad, with the new test files copied in. Never use
stash or restore in this shared checkout. Expect (a) to fail for all six helpers
and (b) to fail for the five unscoped ones (testmap passes (b) already).
For (c)/(d)/(e), the red step proves Step 0 matters in its own right. Run them
against a variant that has Steps 1–2 but **not** Step 0: an isolated copy with
only the `include_absent` call reverted. Expect the baseline-membership and
no-new-commit assertions to fail. Then
remove the scratch worktree.

### 5. Deferred parts of the task: new follow-up tasks, created post-approval

- **install.sh repair wiring.** Calling `setup_data_gitignore_symlink_safe` from
  `install.sh` needs dirty-baseline protection in `commit_installed_files` first.
  That function has none. The task itself says this "should follow the fix
  above". Create a follow-up task (bug, anchor 1711, depends on t1959) to add a
  pre-install dirty baseline to `commit_installed_files`, then call the repair
  before it.
- **cd-guard lint failures.** These are independent of setup, and the failing set
  has grown since the task was written. `bash tests/test_cd_guard_lint.sh` now
  reports 4 `unconfined-andchain` sites and **5** files with no
  `enter_scratch_cwd` (`test_add_model.sh`, `test_list_panes_session_scope_live.sh`,
  `test_opencode_models_merge.sh`, `test_opencode_models_reserved.sh`,
  `test_setup_hooks_only.sh`). The task allows splitting them out. Create a
  separate test-type task listing those sites, with the fix per
  `aidocs/framework/testing_conventions.md`. No existing task owns them (t1832 is
  the leak tripwire, not these sites).
- **Out of scope, noted for the follow-up report.** `setup_data_branch` Step 9
  (`aitask_setup.sh` ~1970) also commits unscoped. Its migration case
  *depends* on that, to carry the staged `git rm -r aitasks/ aiplans/`, so a naive
  pathspec would break it. It runs only on the first data-branch setup. Raise it
  as an upstream-defect follow-up at Step 8b rather than change it here.

## Verification

- `bash tests/test_setup_git.sh`, `bash tests/test_data_branch_setup.sh`,
  `bash tests/test_t167_integration.sh`, `bash tests/test_install_engine_binary.sh`
  all pass.
- Red proof from Step 4 shows the new assertions fail on pre-fix code.
- `shellcheck .aitask-scripts/aitask_setup.sh` is clean (no new findings vs HEAD).
- `grep -n 'git commit -m' .aitask-scripts/aitask_setup.sh`: no remaining
  `.gitignore` helper commit without `-- .gitignore`. Expected remaining hits:
  the data-worktree init (~1826), `setup_data_branch` Step 9 (out of scope,
  above), and the already path-scoped framework commits.

## Step 9 reference

Post-implementation: commit code (`bug: … (t1959)`), plan via `./ait git`, then
archival per task-workflow Step 9.

## Risk

### Code-health risk: low
- The generalized deletion-aware capture (Step 0) changes `commit_framework_files`
  for *any* deleted tracked framework path. Setup used to recreate it and
  commit over the deletion; now it leaves the recreated file uncommitted and
  reports it. This is the baseline contract applied consistently, it is pinned
  by test (e), and the default `_ait_framework_paths` output used for `git add`
  is unchanged · severity: low · → mitigation: none needed beyond the plan (already pinned by Step 4 (e))

The change replaces six near-identical inline commit blocks with
one function, inside one file. Callers keep their messages and their success
output. Existing helper-commit tests run with an unarmed baseline and keep their
behaviour. The new dirty-baseline skip is the intended baseline contract, and
`commit_framework_files` already reports that case.

### Goal-achievement risk: low
None identified. The plan covers both named setup defects for every listed
helper, with a red-proven test per helper. The install.sh wiring and the cd-guard
sites are split into tracked follow-up tasks, which the task text explicitly
allows ("should follow the fix above" / "or split them into their own task").

## Final Implementation Notes
- **Actual work done:** Steps 0–4 as planned. `_ait_framework_paths` gained an `include_absent` second arg (snapshot passes `1`); new `_ait_commit_gitignore_rule` (path-scoped add+commit, skips when `.gitignore` is in `AIT_SETUP_DIRTY_BASELINE`) replaces the six inline commit blocks (messages unchanged); rationale comments refreshed in the testmap header, the `setup_data_gitignore_symlink_safe` header and `main()`. Test 34 (test_data_branch_setup.sh) dirty case now asserts helper rule, repair and user edit all stay out of HEAD; new Test 27 (test_setup_git.sh): 27a/27b × six helpers, 27c/27d staged+unstaged `.gitignore` deletion, 27e deleted-then-regenerated CLAUDE.md through `commit_framework_files`.
- **Deviations from plan:** Step 0 (deletion-aware baseline capture) was added after plan review — the reviewer reproduced that a deleted tracked `.gitignore` never entered the baseline because `_ait_framework_paths` filtered absent paths. Red proof used a `git archive` export of HEAD in the scratchpad instead of a scratch worktree (no git metadata touched).
- **Issues encountered:** In the archive export, T24 and several CLAUDE.md/seed tests fail in both the pre-fix and the Step-0-less runs — the export lacks `seed/`; they pass in the real tree. Verified git accepts unmatched and symlink-traversing pathspecs in `ls-files --others/--modified` and `diff --cached` (exit 0, no output), and reports an unstaged deletion under `--modified` and a staged one under `--cached`.
- **Key decisions:** Kept per-helper commits (descriptive messages) rather than deferring all writes to `commit_framework_files`. Fixed the deletion gap in the shared capture, not per helper, so `commit_framework_files` also stops committing a regenerated file over a pre-setup deletion (pinned by 27e). Red proofs: pre-fix → 27a fails for all six helpers, 27b for the five unscoped ones, 27c/d/e and 34a fail; fix-minus-Step-0 → only 27c/d/e fail.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_setup.sh:1970-1985 — setup_data_branch Step 9 commits with an unscoped git commit (whole-index sweep) and ignores the dirty baseline; its migration branch relies on the unscoped commit to carry the staged git rm -r aitasks/ aiplans/, so a naive pathspec would break it`
  - `install.sh:1167 — commit_installed_files has no pre-install dirty baseline, so ait upgrade cannot safely run setup_data_gitignore_symlink_safe (the legacy .aitask-data/ line survives upgrade-only installs)`
  - `tests/test_cd_guard_lint.sh — fails on main: unconfined-andchain at tests/test_aitasks_home.sh:319, tests/test_install_engine_binary.sh:224, tests/test_setup_hooks_only.sh:74, tests/test_upgrade_prunes_retired_scripts.sh:73; no enter_scratch_cwd in tests/test_add_model.sh, test_list_panes_session_scope_live.sh, test_opencode_models_merge.sh, test_opencode_models_reserved.sh, test_setup_hooks_only.sh`
