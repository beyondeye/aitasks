---
priority: medium
effort: medium
depends: [t1747_4]
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1733
created_at: 2026-09-09 11:14
updated_at: 2026-09-09 11:14
---

## Context

Child of t1747 (full audit: `aiplans/p1747_sweep_failopen_git_probes.md`; the
rule and canonical fix shape: `aidocs/framework/failopen_git_probes.md`, landed
by t1747_1).

Covers **audit rows A6 and A7** — the published-history clause of the two amend
guards. This is the *sibling* of the probe t1733 and t1599_4 already fixed: the
hardened pattern sits about 40 lines **above** each of these, in the same
function, in the same file. This is a copy-the-sibling change.

## The defect (identical in both files)

`.aitask-scripts/aitask_fold_mark.sh::_fold_amend_guard` (~:961) and
`.aitask-scripts/aitask_issue_import.sh::_import_amend_guard` (~:686):

```bash
    ups="$(task_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
    if [[ -n "$ups" ]] && task_git merge-base --is-ancestor HEAD "$ups" 2>/dev/null; then
        <refuse: amending would rewrite pushed history>
    fi
    return 0
```

This gates **`task_git commit --amend --no-edit -o`** — a history rewrite. Two
distinct holes:

1. **`|| true` conflates "no upstream configured" with "rev-parse failed"**
   (a bad `.git/config`, a detached data worktree, `task_git` erroring). An
   empty `ups` short-circuits the **entire** published-history check away, and
   the guard `return 0`s — amend authorized.
2. **`merge-base --is-ancestor` returns 0/1 for the real answers and ≥2 for
   errors.** The `if` treats every non-zero identically as "not published", so a
   probe error also authorizes the amend.

**The existing "ACCEPTED RESIDUAL" comment does not cover this.** It documents
only *staleness* of the local remote-tracking ref (the guard deliberately does
not fetch), and correctly claims that staleness "can under-detect a published
commit; it can never wrongly refuse an unpublished one". Probe *failure* is a
different thing and is un-audited. Amend the comment to say which residual
actually remains after this fix.

## Fix

Mirror the already-hardened probe in each file (`aitask_fold_mark.sh:915`,
`aitask_issue_import.sh:650`) — capture the status separately, and distinguish
the three outcomes of `--is-ancestor`:

```bash
    local ups="" ups_rc=0
    ups="$(task_git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" || ups_rc=$?
    # rc 128 = no upstream configured (a real, safe answer). Anything else is a
    # probe failure: unverified, never "unpublished".
    …
    if [[ -n "$ups" ]]; then
        local anc_rc=0
        task_git merge-base --is-ancestor HEAD "$ups" 2>/dev/null || anc_rc=$?
        case $anc_rc in
            0) <refuse: published> ;;
            1) : ;;                       # genuinely not an ancestor
            *) <refuse: ancestry unverified> ;;
        esac
    fi
```

**Establish empirically which rc `rev-parse '@{u}'` returns for a genuinely
unconfigured upstream** before writing the branch — do not assume 128. If that
rc is not cleanly separable from a general failure, say so and fall back to
refusing on any non-zero, noting that a repo with no upstream then cannot use
`--commit-mode amend`; check first whether any production caller hits that case.

Follow each file's existing refusal shape (`_fold_amend_refusal` /
`_import_amend_refusal`, with `Re-run with --commit-mode fresh.` in the fold
file). The guards never `die()` themselves — the caller rolls back first.

## Call-site table (required by the parent's shared contract)

Both guards are single-consumer, but confirm that rather than assume it, and
record it. Also check whether the same `@{u}` shape appears elsewhere in either
file.

## Verification

Both files already have the right harness and the right precedent tests —
`tests/test_fold_mark.sh` (t1733 block: three tests + three negative controls)
and `tests/test_issue_import_amend_guard.sh` (A6a/A6b). Extend those, do not
start new files.

- **Discriminating fixture:** a HEAD the guard would otherwise **permit** — a
  single-parent commit carrying only the operation's own paths, on a branch with
  an upstream that does **not** contain it — under a `PATH` `git` shim that
  fails only `rev-parse … @{u}` (and a second variant failing only
  `merge-base --is-ancestor` with rc ≥2). That is what proves a failed probe does
  not authorise a rewrite, rather than merely coinciding with a refusal.
  `tests/test_fold_mark.sh::install_failing_show_shim` is the shim pattern; note
  it lives outside the fixture repo so it cannot appear as an untracked path.
- **Preconditions asserted** in the test *and* its control: unshimmed, HEAD is
  single-parent, lists exactly the operation's own paths, and is **not** an
  ancestor of the upstream (so the guard permits); shimmed, the probe exits
  non-zero.
- **Fail-closed:** exit non-zero, the refusal names the unverified state, and
  **HEAD's SHA is unchanged**.
- **Negative control** against a probe-only mutant restoring the `|| true`
  shape: the amend proceeds and **HEAD is rewritten**. Use
  `install_prefix_amend_probe`'s technique — verify the substitution landed and
  assert the rest of the guard (the foreign-path refusal, the function itself)
  survived, so the control observes a fail-open guard rather than no guard.
- **Permit direction stays green:** `test_amend_permits_labels_file_in_head`,
  `test_amend_permits_child_primary_parent_file`, `test_fresh_mode_full_flow`,
  and the issue-import A-series. In particular a repo with **no upstream
  configured** must still permit the amend — that is the case hole 1 conflates,
  and breaking it would make the fix a regression for every un-pushed checkout.

```bash
bash tests/test_fold_mark.sh
bash tests/test_issue_import_amend_guard.sh
bash tests/test_merge_issues.sh
shellcheck .aitask-scripts/aitask_fold_mark.sh .aitask-scripts/aitask_issue_import.sh
```

Note `aitask_issue_import.sh` runs `set -e` **without** `-u`/`pipefail`, unlike
the rest of the family — check idioms against that before copying them across.
Shellcheck baseline for both files: only pre-existing SC1091 / SC2012
informational findings.
