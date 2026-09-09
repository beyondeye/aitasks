---
Task: t1747_5_published_history_amend_probes.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1747_5 — The published-history clause of both amend guards

## Context

Audit rows A6 + A7 (see `aidocs/framework/failopen_git_probes.md`). This is the
**sibling** of the probe t1733 and t1599_4 already hardened: the fixed pattern
sits ~40 lines above each of these, in the same function, in the same file. A
copy-the-sibling change, in `aitask_fold_mark.sh` (~:961) and
`aitask_issue_import.sh` (~:686).

## The defect (identical in both)

```bash
    ups="$(task_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
    if [[ -n "$ups" ]] && task_git merge-base --is-ancestor HEAD "$ups" 2>/dev/null; then
        <refuse: amending would rewrite pushed history>
    fi
    return 0
```

Gates **`task_git commit --amend --no-edit -o`** — a history rewrite. Two holes:

1. `|| true` conflates "no upstream configured" with "rev-parse failed" (bad
   `.git/config`, detached data worktree, `task_git` erroring). Empty `ups`
   short-circuits the **whole** published-history check away ⇒ amend authorized.
2. `merge-base --is-ancestor` returns 0/1 for the real answers and **≥2 on
   error**; the `if` treats every non-zero as "not published" ⇒ amend authorized.

**The existing "ACCEPTED RESIDUAL" comment does not cover this.** It documents
only *staleness* of the local remote-tracking ref (the guard deliberately does
not fetch) and correctly claims staleness "can under-detect a published commit;
it can never wrongly refuse an unpublished one". Probe *failure* is a different
thing and is un-audited. Amend the comment to state which residual actually
remains after this fix — leaving it as-is would make the docs claim a hole is
accepted when it is now closed.

## Implementation

### 1. Establish the "no upstream" exit code empirically — before writing the branch

Do not assume 128. In a scratch repo, run
`git rev-parse --abbrev-ref --symbolic-full-name '@{u}'` on a branch with no
upstream and record the rc. Then:

- **If it is cleanly separable** from a general failure → treat that rc as the
  real answer "no upstream" and every other non-zero as unverified ⇒ refuse.
- **If it is not separable** → say so explicitly and refuse on any non-zero,
  *after* checking whether any production caller of `--commit-mode amend`
  actually runs without an upstream. The three known callers (`aitask-explore`,
  `aitask-pr-import`, `aitask-contribution-review`) amend a task-creation commit
  they just made; establish whether the data branch always has an upstream
  there. Record the finding either way — this is the decision most likely to
  turn the fix into a regression.

### 2. The fix shape

```bash
    local ups="" ups_rc=0
    ups="$(task_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" || ups_rc=$?
    # <handle the no-upstream rc established in step 1; any other non-zero refuses>
    if [[ -n "$ups" ]]; then
        local anc_rc=0
        task_git merge-base --is-ancestor HEAD "$ups" 2>/dev/null || anc_rc=$?
        case $anc_rc in
            0) <refuse: published on $ups> ;;
            1) : ;;                        # genuinely not an ancestor
            *) <refuse: ancestry unverified> ;;
        esac
    fi
```

Follow each file's existing refusal shape — `_fold_amend_refusal` /
`_import_amend_refusal`, with `Re-run with --commit-mode fresh.` in the fold
file. Neither guard `die()`s itself; the caller rolls back first
(`aitask_fold_mark.sh:1020-1024`).

Comments **point at** `aidocs/framework/failopen_git_probes.md` rather than
restating the rule a fifth time.

### 3. Watch the shell options

`aitask_issue_import.sh` runs `set -e` **without** `-u`/`pipefail`, unlike the
rest of the family. Check each idiom against that before copying it across; the
two files are not interchangeable.

## Call-site table

Both guards look single-consumer — confirm rather than assume, and record it.
Also grep both files for any other `@{u}` / `--is-ancestor` use.

## Verification

Extend the existing suites and their precedents — `tests/test_fold_mark.sh`
(t1733 block: 3 tests + 3 controls) and `tests/test_issue_import_amend_guard.sh`
(A6a/A6b). Do not start new files.

### The discriminating fixture

A HEAD the guard would otherwise **permit**: a single-parent commit carrying
only the operation's own paths, on a branch whose upstream does **not** contain
it — under a `PATH` `git` shim failing only `rev-parse … @{u}`, and a second
variant failing only `merge-base --is-ancestor` with rc ≥2. This is what proves
a failed probe does not authorise a rewrite, rather than coinciding with a
refusal that would have happened anyway.

`tests/test_fold_mark.sh::install_failing_show_shim` is the shim pattern — note
it lives **outside** the fixture repo so it cannot appear as an untracked path.

### Preconditions, asserted in the test AND its control

- unshimmed: HEAD is single-parent, lists exactly the operation's own paths, and
  is **not** an ancestor of the upstream — i.e. the guard permits;
- shimmed: the probe exits non-zero.

### Assertions

| direction | assertion |
|---|---|
| fail-closed | exit non-zero; the refusal names the unverified state; **HEAD's SHA is unchanged** |
| negative control | against a probe-only mutant restoring `\|\| true`: the amend proceeds and **HEAD is rewritten** (`assert_defect_present`) |
| permit | `test_amend_permits_labels_file_in_head`, `test_amend_permits_child_primary_parent_file`, `test_fresh_mode_full_flow`, and the issue-import A-series stay green — **and a repo with no upstream configured still permits the amend**, which is the case hole 1 conflates and the one most likely to regress |

The mutant installer must verify its substitution landed and assert the rest of
the guard survived (the foreign-path refusal, the function itself), so the
control observes a fail-open guard rather than no guard at all.

```bash
bash tests/test_fold_mark.sh
bash tests/test_issue_import_amend_guard.sh
bash tests/test_merge_issues.sh
shellcheck .aitask-scripts/aitask_fold_mark.sh .aitask-scripts/aitask_issue_import.sh
```

Baseline for both: only pre-existing SC1091 / SC2012 informational findings.

## Risk

### Code-health risk: low
- Two ~15-line clauses, each mirroring a hardened probe already in the same
  function. · severity: low · → mitigation: none needed.

### Goal-achievement risk: medium
- If the "no upstream" rc is not separable, refusing on any non-zero would break
  `--commit-mode amend` for every checkout without an upstream — turning a
  fail-open fix into a fail-closed regression. · severity: medium · →
  mitigation: none needed as a task — step 1 makes the measurement a
  precondition of writing the branch, and the permit test pins the no-upstream
  case in both files.
