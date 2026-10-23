---
Task: t2132_symbolic_ref_short_head_tag_ambiguity.md
Base branch: main
Output branch: main
---

# t2132 — read HEAD as a full ref wherever its branch name is consumed

## Context

`git symbolic-ref --short HEAD` **and** `git rev-parse --abbrev-ref HEAD` both
abbreviate by ambiguity. When a tag has the same name as the checked-out branch
(tag `dev` beside branch `dev`), both return `heads/dev`, and no caller can use
that as a branch name. I reproduced this on git 2.56:
`short=heads/dev abbrev=heads/dev`. t2123 fixed the `origin/HEAD` variant, and
t2124 (in flight, uncommitted in the working tree) is fixing
`aitask_plan_externalize.sh`. Both use the same idiom: read the **full** ref,
accept it only under `refs/heads/`, and treat anything else as "no branch".

The user widened scope at planning time. The task's 5 listed `symbolic-ref --short`
sites are joined by the `rev-parse --abbrev-ref HEAD` sites found in the sweep.
Each consumer that acts on the value gets a tag-beside-branch regression with a red
proof. Display-only sites get the fix plus a recorded red/green probe.

`aitask_plan_externalize.sh` is **out of scope**: t2124 owns it, and its working-tree
diff is another session's work. Do not touch it.

Probed exit codes for `git symbolic-ref --quiet HEAD` (git 2.56): `0` + `refs/heads/<b>`
when HEAD is on a branch, `1` when detached, `128` outside a repository.

## Idiom (inline at every bash site, matching t2124 / t2123)

```bash
# Full ref, never --short / --abbrev-ref: both abbreviate by ambiguity, so a tag
# named like the branch turns the answer into "heads/<b>" (t2132).
ref="$(git symbolic-ref --quiet HEAD 2>/dev/null || true)"
case "$ref" in
    refs/heads/?*) branch="${ref#refs/heads/}" ;;
    *)             branch="" ;;               # detached / unexpected → site's existing fallback
esac
```

The idiom stays inline rather than in a new shared helper. `aitask_merge_task.sh`
and `aitask_task_worktree.sh` source only `terminal_compat.sh`, and test fixtures
copy explicit lib subsets (e.g. `tests/lib/metadata_update_fixture.sh`). A new
`source` would break those fixtures, as the source-on-startup rule warns.

## Implementation steps

Order: **write each regression first and run it red against the unfixed code. Then
apply the fix and run it green.** Do not stash or restore to get the baseline: the
tree is shared and holds t2124's uncommitted work.

### A. Listed `symbolic-ref --short` sites

1. **`.aitask-scripts/aitask_merge_task.sh:84` `_head_branch()`.** Apply the idiom
   (print the stripped name, or nothing). Its consumers compare it with
   `out_branch` (`PREFLIGHT_HEAD_MISMATCH` at :199-201, abort's `ABORT_FAILED` at
   :255) or test it for emptiness (:266, :411, :424). Emptiness on detached HEAD
   stays the same.
   - Test: `tests/test_merge_lock_broker.sh` gets a new case `case_t2132`.
     `new_repo`, then `git tag main`. Fixture precondition:
     `git symbolic-ref --short HEAD` == `heads/main`.
     `begin tA main aitask/tclean` → `MERGE_OK:` (unfixed:
     `PREFLIGHT_HEAD_MISMATCH:main:heads/main`), then `finish`. A second repo:
     `begin tA main aitask/tconf` → `MERGE_CONFLICT`, then `abort` → `ABORTED`
     (unfixed: `ABORT_FAILED`).
2. **`.aitask-scripts/aitask_task_worktree.sh:392` `head_ref`.** Apply the idiom,
   keeping the `HEAD` fallback when there is no branch. The value appears in the
   user-facing `BRANCH_KEPT unmerged_into:<ref>` (task-abort.md:118).
   - Test: `tests/test_task_worktree_helper.sh` gets a new case beside Case 11.
     Same setup, plus `git tag "$PRIMARY"` and the precondition assert →
     `BRANCH_KEPT unmerged_into:$PRIMARY aitask/tA`.
3. **`.aitask-scripts/aitask_sync.sh:1954` `_sync_afx_data_ref`.** Apply the idiom
   in the data worktree and `return 1` when the branch is empty. Unfixed, this
   **fails open**: the guard fetches `refs/heads/heads/<db>`, `ls-remote` answers
   "absent" (exit 2), the record is treated as "no remote data branch", and the
   broad fetch downloads the store.
   - Test: `tests/test_sync_fetch_exclusion.sh` gets a new case 10. `world`, then
     `git -C "$Y" tag aitask-data aitask-data`, then the precondition
     `git -C "$Y/.aitask-data" symbolic-ref --short HEAD` == `heads/aitask-data`.
     Then `xstore store-a` + `xpub store-a store-a` + `run_sync`. Assert the store
     commit was **not** downloaded (`has_obj` → `no`) and
     `^refs/heads/store-a` is excluded (unfixed: downloaded).
4. **`.aitask-scripts/lib/task_utils.sh:820` (`task_git_pull` rebase-mode
   resolution).** Apply the idiom with `_ait_data_git`. Unfixed, the key becomes
   `branch.heads/<b>.rebase`. That misses the branch's config, so an interactive
   `branch.<b>.rebase` is **not refused**.
   - Test: `tests/test_ait_git_gateway_pull.sh` Test H. After the
     `branch.aitask-data.rebase=i` row, add
     `git -C "$DATA" tag aitask-data` with the precondition assert, then
     `run_ait pull; h_refused "branch config with a same-named tag"`, then
     delete the tag before the existing unset lines.
5. **`.aitask-scripts/lib/shadow_scope.py:244` `dedicated_worktree`.** Read
   `symbolic-ref --quiet HEAD`, decode, and accept only the `refs/heads/` prefix
   with a non-empty remainder. Compare that remainder with `aitask/<task_name>`.
   - Test: `tests/test_shadow_scope.sh` Fixture C, after `outO`. Add
     `git -C "$C" tag aitask/t7_x aitask/t7_x` plus the precondition
     (`heads/aitask/t7_x`). Re-run `scope "$C" 7 --checkout wt_ded` and expect
     `SIGNAL:dedicated_worktree|yes|branch` (unfixed: `|no`). Then delete the tag.

### B. `rev-parse --abbrev-ref HEAD` sites (scope widened by the user)

6. **`.aitask-scripts/lib/verified_update_lib.sh:76` `current_task_branch`.**
   Keep the two outcomes distinct. If `./ait git symbolic-ref --quiet HEAD`
   exits `1`, keep the existing detached-HEAD `die` message. Any other non-zero
   exit → `die "could not resolve HEAD of the task data worktree"`. Otherwise strip
   `refs/heads/`, and if the prefix does not match, use the detached message.
   Unfixed, `git clone --branch heads/<b>` fails (:189), so the usage/verified bump
   is lost. `has_remote_tracking` (:73) only checks that the command succeeded,
   so it is left as is.
   - **Also qualify the push destination.**
     `commit_and_push_from_remote_clone` (:225) pushes `"HEAD:${branch}"`. When the
     **origin** has both `refs/heads/<b>` and `refs/tags/<b>`, even the corrected
     name fails with `dst refspec <b> matches more than one`. The error text
     contains `failed to push some refs`, so `is_retryable_push_error` also burns
     every retry on it. Change it to `"HEAD:refs/heads/${branch}"`. A probe on git
     2.56 confirmed this: `HEAD:main` → rc 1, `HEAD:refs/heads/main` → rc 0 with
     the tag preserved. `clone --branch <b>` already resolves to the branch in the
     same situation (probed: `refs/heads/main`), so the clone line stays. A sweep
     for unqualified `push … HEAD:$var` destinations under `.aitask-scripts/` finds
     only this site.
   - Test: `tests/test_verified_update.sh` gets a new test.
     `setup_remote_repo`. Create tag `main` at the seed commit in `work`, and
     **publish it to origin with an explicit refspec**
     (`git push origin refs/tags/main:refs/tags/main`). Fixture preconditions:
     `rev-parse --abbrev-ref HEAD` in `work` == `heads/main`, and origin has both
     `refs/heads/main` and `refs/tags/main`. Run the remote path, invoked the same
     way as Test 9. Assert:
     - exit 0;
     - origin's `refs/heads/main` advanced to a commit carrying the update;
     - origin's `refs/tags/main` still names the original commit (preserved);
     - the local branch contains the pushed commit, i.e. the converge invariant
       held and no `not on the local data branch` warning appeared.
     Red proof in two stages. With neither fix: "Failed to clone task data branch
     'heads/main'". With only the branch-name fix:
     `dst refspec main matches more than one`. Both stages must fail before the
     final green. If the converge assertion exposes the same ambiguity inside
     `task_data_converge`, fix it here too (same defect class, same rule:
     qualify it as `refs/heads/…`), using this same test as its red proof.
7. **`.aitask-scripts/aitask_metadata_commit.sh:150` preflight `BRANCH:`.**
   `task_git symbolic-ref --quiet HEAD`. Exit `0` + `refs/heads/<b>` →
   `BRANCH:<b>`. Exit `0` with another prefix, or exit `1` → `BRANCH:DETACHED`.
   Any other exit → the existing `FAILED:cannot resolve HEAD …` line. This
   preserves the comment's "a failing inspection is never detached" contract.
   - Test: `tests/test_metadata_commit_seam.sh` case 12 shape. Tag `aitask-data`
     in the data worktree + precondition, then `--preflight`. Assert a line that
     is **exactly** `BRANCH:aitask-data` (`grep -qx`). A substring match is not
     enough: `BRANCH:heads/aitask-data` does not contain it, but a later edit could
     make the substring check pass by accident. Add a detached control:
     `git -C .aitask-data checkout --detach` → exactly `BRANCH:DETACHED`. (The old
     code printed `DETACHED` for rev-parse's literal `HEAD` answer. This proves
     the rc=1 mapping keeps that.)
8. **`.aitask-scripts/aitask_note.sh:397` `PROV_BASE_BRANCH`.** Apply the idiom.
   Empty → the existing `unknown`. A detached HEAD used to record the literal
   `HEAD`; record `HEAD` again in that case so the provenance vocabulary does not
   change. The value is compared with `detect_primary_branch` (:406) and written
   as `base_branch=` (:1499).
   - Test: `tests/test_note_append.sh` case 8 shape. `git -C "$MASTER" tag feature`
     + precondition, send a note, then assert `base_branch=feature` (unfixed:
     `base_branch=heads/feature`).
9. **Display-only sites:** `.aitask-scripts/lib/task_utils.sh:523`
   (`task_git_health`, `?` fallback) and `.aitask-scripts/aitask_lock_diag.sh:175`
   (`unknown` fallback). Apply the idiom. Detached → `HEAD`, as before. Change the
   `task_git_health` label from `Branch (rev-parse --abbrev-ref HEAD):` to
   `Branch:`. No test or doc references it (grepped). **No permanent tests.**
   Record a red/green probe verbatim in Final Implementation Notes: a scratch
   branch-mode repo with a same-named tag, run `./ait git-health` and
   `aitask_lock_diag.sh` before and after the fix.

### C. Close-out

10. Re-grep `.aitask-scripts/` for `symbolic-ref .*--short`, `--short .*HEAD` and
    `abbrev-ref HEAD`. The only hits left should be
    `aitask_plan_externalize.sh` (t2124) and `has_remote_tracking` (existence
    check). Record the grep and its result in Final Implementation Notes.
11. Shellcheck every touched `.sh` file.

## Verification

Each suite gets **its own** `bash` invocation. `bash a.sh b.sh` runs only `a.sh`
and passes the rest as arguments, which these files ignore. Check each exit
status separately:

```bash
rc_all=0
for t in test_merge_lock_broker test_task_worktree_helper test_sync_fetch_exclusion \
         test_ait_git_gateway_pull test_shadow_scope test_verified_update \
         test_metadata_commit_seam test_note_append \
         test_task_git test_lock_diag test_usage_update; do   # last three: untouched neighbours
    bash "tests/$t.sh" >/tmp/claude-1000/t2132_$t.log 2>&1; rc=$?
    echo "$t rc=$rc"; [[ $rc -eq 0 ]] || rc_all=1
done
echo "ALL rc=$rc_all"
shellcheck .aitask-scripts/aitask_merge_task.sh .aitask-scripts/aitask_task_worktree.sh \
  .aitask-scripts/aitask_sync.sh .aitask-scripts/lib/task_utils.sh \
  .aitask-scripts/lib/verified_update_lib.sh .aitask-scripts/aitask_metadata_commit.sh \
  .aitask-scripts/aitask_note.sh .aitask-scripts/aitask_lock_diag.sh
```

Before each fix, the new regressions must fail on the asserts this plan names
(red proof). After the fixes, every file prints its own PASS. Commit with
`bug: Read HEAD as a full ref wherever its branch name is consumed (t2132)`,
naming only the touched paths, with no `aitask_plan_externalize.sh` or other
t2124 paths. Then Step 9 (Post-Implementation) archives the task.

## Risk

### Code-health risk: medium
- Old commands and the new idiom handle detached HEAD and errors differently.
  `rev-parse --abbrev-ref` *succeeded* with `HEAD` on a detached HEAD, and
  `symbolic-ref --quiet` exits 1. At the three sites that keep that distinction
  (metadata-commit preflight, verified_update_lib, note provenance), a careless
  swap could turn "detached" into "failed" or the reverse · severity: low (each
  site maps rc=1 explicitly, and step 7 pins `BRANCH:DETACHED` with a detached
  control) · → mitigation: none (covered in-plan by steps 6-8)
- The change touches load-bearing paths (merge broker, sync fetch guard, pull
  gateway) across 9 files. Each edit swaps an idiom in one place, and each site
  keeps its fallback · severity: low · → mitigation: none (each site has a
  regression; the untouched neighbouring suites are re-run)

### Goal-achievement risk: low
- Fixing how HEAD is *read* is not enough when the tag is also **published**: an
  unqualified destination like `HEAD:<b>` stays ambiguous on the remote (found in
  review and confirmed by probe) · severity: low (step 6 qualifies the push as
  `refs/heads/…`; its fixture publishes the tag and needs a two-stage red proof;
  the sweep found no other unqualified push destination) · → mitigation: none
  (covered in-plan by step 6)
