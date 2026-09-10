---
priority: high
effort: high
depends: [t1747_2]
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
anchor: 1733
created_at: 2026-09-09 11:13
updated_at: 2026-09-09 11:13
---

## Context

Child of t1747 (full audit: `aiplans/p1747_sweep_failopen_git_probes.md`; the
rule and canonical fix shape: `aidocs/framework/failopen_git_probes.md`, landed
by t1747_1).

Covers **audit rows A3, A4, A5 and A10** — four fail-open authorization probes
in `.aitask-scripts/aitask_sync.sh`. Grouped because they share one file and one
test harness; each still gets its own control.

## The four defects

### A3 — `:772` shared-index staged guard (`_commit_group`)

```bash
    staged="$(task_git diff --cached --name-only -- "${paths[@]}" 2>/dev/null)" || staged=""
    if [[ -n "$staged" ]]; then
        _protect "staged_elsewhere" "…group deferred"; return 0
    fi
```

A failed probe reads as "nobody staged anything" and the group proceeds to
`task_git add` / `commit -o` / the failure-path `reset` (:817). The harm is
named in the code's own comment directly above: *"`add` would replace it and
`reset` would remove it, destroying in-flight work."* The guard is disarmed by
precisely the condition (index contention) that makes the hazard likely.
Disposition: a failed probe is **unverified** ⇒ `_protect` and defer the group,
the same as a positive detection.

### A4 — `:503` quarantine-release settlement clause

```bash
            if [[ "$verdict" == "free" || "$verdict" == "dead" ]] \
               && [[ -z "$(task_git status --porcelain -- "$p" 2>/dev/null)" ]]; then
                iinfo_err "quarantine released (owner gone, state settled): $p"; continue
```

Command-substitution failure is invisible inside `[[ -z … ]]`, so an
**unreadable** worktree reads as clean ⇒ the entry is dropped from
`QUARANTINE_HELD` / `PUBLICATION_BLOCKED` and a commit the framework
deliberately withheld gets pushed. The comment immediately above argues at
length that a clean worktree is not settlement on its own — this closes the
matching hole for an unreadable one. Disposition: unverified ⇒ **hold** (never
release).

### A5 — `:919` conflict-vs-other-error classifier (`do_pull_rebase`)

```bash
        conflicted=$(task_git diff --name-only --diff-filter=U 2>/dev/null || true)
        if [[ -n "$conflicted" ]]; then … else <unconditional rebase --abort> fi
```

Empty reads as "not a conflict" ⇒ aborts a real in-progress conflict resolution.
Recoverable via `ORIG_HEAD`, but it silently throws away merge work. Disposition:
unverified ⇒ a distinct diagnostic, not a silent abort down the "some other
pull/rebase error" path.

### A10 — `:301` `_sync_gitdir` silent `.git` fallback

```bash
_sync_gitdir() {
    local gd; gd="$(_ait_data_gitdir)"
    if [[ -z "$gd" ]]; then gd="$(git rev-parse --git-dir 2>/dev/null)" || gd=".git"; fi
    printf '%s' "${gd:-.git}"
}
```

A fabricated `.git` makes every `[[ -e "$gd/rebase-merge" ]]` test miss ⇒
`_worktree_wedged` reads "not wedged" ⇒ sync proceeds to auto-commit and push
over a wedged worktree. It **also** relocates `_quarantine_path`, and
`_quarantine_load` returns early on a missing/empty file (`[[ -s "$qf" ]] || return 0`),
so **every held quarantine entry is silently lost** — releasing withheld commits
for publication by accident. Disposition: an unresolvable git-dir is
**unverified** ⇒ refuse at the helper; never substitute a default that composes
into a path.

## Call-site tables (required by the parent's shared contract)

A10 in particular is not a single-consumer fix: `_sync_gitdir` has two direct
consumers (`_worktree_wedged:343`, `_quarantine_path:306`) and
`_quarantine_path` fans out to four more sites. Enumerate every consumer of each
changed helper, state its disposition on "unverified", and ship a test asserting
the file's actual call sites equal the table — so a new consumer cannot be added
bare.

## Verification

Per the parent's shared contract, each of the four sites gets:

- a **fail-closed test** driven by an argv-keyed `PATH` `git` shim that fails
  exactly one verb (`diff --cached`, `status --porcelain`,
  `diff --diff-filter=U`, `rev-parse --git-dir`), scoped so it does not abort the
  run before the probe is reached — see `install_failing_add_shim` in
  `tests/test_sync_branch_mode_automerge.sh` for the scoping technique;
- an **asserted fixture precondition**, in the test *and* its control: pin both
  the fixture's identity and its symptom, since "the probe returned empty" is a
  symptom several unrelated fixture accidents produce. For A3, assert that
  unshimmed the paths really are staged by a second session; for A4, that the
  entry really is quarantined and the holder really is free/dead; for A10, that
  unshimmed the git-dir resolves and the quarantine file is non-empty;
- a **production-reachable discriminating case** where the action **would
  otherwise have proceeded**, so the test proves the failed probe is what
  stopped it;
- a **negative control** against a probe-only mutant, following
  `tests/test_fold_mark.sh::install_prefix_amend_probe` (verify the substitution
  landed; assert the rest of the guard survived);
- the **permit direction green** — a deferred group must still commit normally,
  a genuinely settled quarantine entry must still release, a real conflict must
  still reach resolution, and a healthy worktree must still sync.

A10's control must specifically assert that a held quarantine entry **survives**
the fix (pre-fix it vanishes with the relocated file).

```bash
bash tests/test_sync_branch_mode_automerge.sh
bash tests/test_sync.sh
bash tests/test_sync_auto_commit_scoping.sh
bash tests/test_sync_deferral_and_quarantine.sh
bash tests/test_sync_branch_mode_automerge.sh
bash tests/test_no_unscoped_task_commit.sh
shellcheck .aitask-scripts/aitask_sync.sh
```

Shellcheck baseline: `aitask_sync.sh` is clean apart from SC1091. New code must
add none.

## Note on splitting

Four guards is a lot for one change. If the diff becomes unreviewable, A4+A10
(the pair that both end in publishing something the framework withheld) and
A3+A5 are the natural cut — but keep them one task unless it actually becomes a
problem, since they share a test harness.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1747_1** id=2026-09-09T13:33:17Z.df3139bfa0d60e3df3c0bdc5 from=t1747_1 from_verified=yes at=2026-09-09T13:33:17Z base=e7e9fcb9a5672cd47728cc209d124f265c7c08f7 base_branch=main dirty=yes host=omg16
>
> | Blast-radius warning about your target file, measured 2026-09-09 at HEAD
> | e7e9fcb9a. This is a working-tree observation, so it is moment-relative and may
> | already have changed.
> | 
> | `.aitask-scripts/aitask_sync.sh` is currently DIRTY in this shared worktree with
> | roughly +392 uncommitted lines from another live session (t1725_3, "Characterize
> | every _protect path's batch stdout"): 1202 lines at HEAD vs 1594 on disk.
> | Functions have already moved substantially in that working copy, e.g.
> | `_commit_group` 763 -> 993, `_sync_gitdir` 297 -> 368, `do_pull_rebase` ~910 ->
> | 1246.
> | 
> | Two consequences for this task:
> | 
> | 1. Every `aitask_sync.sh` line number the t1747 audit gives you (A3 :772,
> |    A4 :503, A5 :919, A10 :301, and the negative-space rows :1004/:1009/:1015)
> |    is correct against HEAD and WRONG against that working copy. Re-resolve by
> |    function name (`_commit_group`, `_quarantine_load_and_prune`,
> |    `do_pull_rebase`, `_sync_gitdir`) rather than by line before you edit.
> | 2. You will be editing a file another session is actively restructuring.
> |    Consider checking whether t1725_3 has landed before you start.
> | 
> | `aidocs/framework/failopen_git_probes.md` (t1747_1) is the canonical anchor for
> | the rule, the fix shape and your four Group A rows; it anchors on
> | file::function for exactly this reason. Point at it rather than restating.

> **👁 note:read** id=2026-09-10T12:39:16Z.3f4062bc921e24bc2c377115 by=t1747_3 at=2026-09-10T12:39:16Z mode=explicit ids=2026-09-09T13:33:17Z.df3139bfa0d60e3df3c0bdc5
