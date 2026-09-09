---
priority: high
effort: medium
depends: [t1747_3]
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

Covers **audit rows A9 and A9b** in `.aitask-scripts/aitask_setup.sh` — the
second of the two candidates the t1747 task body names.

## A9 — `_ait_list_framework_changes` (~:3584-3597)

```bash
    untracked="$(git -C "$workdir" ls-files --others --exclude-standard -- "$@" 2>/dev/null)" || true
    modified="$(git -C "$workdir" ls-files --modified -- "$@" 2>/dev/null)" || true
    staged="$(git -C "$workdir" diff --cached --name-only -- "$@" 2>/dev/null)" || true
    printf '%s\n%s\n%s\n' "$untracked" "$modified" "$staged" \
        | sed '/^$/d' | sort -u | grep -Ev "$exclude_re" || true
```

**The function is consumed in two opposite polarities, and only one is safe.**

| call | line | polarity | probe-failure effect |
|---|---|---|---|
| baseline snapshot, main tree | ~3654 | **subtrahend** | empty baseline ⇒ `_ait_subtract` removes nothing ⇒ `commit_framework_files` **sweeps the user's pre-existing uncommitted work into an `ait:` framework commit**. Fail-OPEN |
| baseline snapshot, data tree | ~3666 | **subtrahend** | same, via `commit_framework_data_files`. Worse: that function's own comment says concurrent sessions "routinely have in-progress work" in the data worktree |
| change list, main | ~3707 | minuend | empty ⇒ nothing committed, reported as `success "All framework files already committed to git"`. Not destructive, but a **false success** |
| change list, data | ~3865 | minuend | same |
| post-commit `still_untracked` | ~3804 | display | informational; leave as-is |

The header comment states the staged term exists so the commit does not "sweep
the user's staged hunk" — and the next line lets `2>/dev/null || true` do exactly
that on any git failure.

### Fix

Give the helper a real exit status. **The trailing `|| true` on the
`printf | sed | sort | grep -Ev` pipeline is load-bearing and must stay** —
`grep -Ev` exits 1 on a legitimately empty result. Only the three `git` captures
need rc capture:

```bash
    local untracked modified staged probe_rc=0
    untracked="$(git -C "$workdir" ls-files --others --exclude-standard -- "$@" 2>/dev/null)" || probe_rc=1
    modified="$(git -C "$workdir" ls-files --modified -- "$@" 2>/dev/null)"          || probe_rc=1
    staged="$(git -C "$workdir" diff --cached --name-only -- "$@" 2>/dev/null)"      || probe_rc=1
    printf '%s\n%s\n%s\n' "$untracked" "$modified" "$staged" \
        | sed '/^$/d' | sort -u | grep -Ev "$exclude_re" || true
    (( probe_rc == 0 )) || return 2
```

Every one of the four call sites absorbs it with `|| rc=$?`, declaring
`local rc=0` on its **own line** first (`local x="$(…)" || rc=$?` captures
`local`'s status, not the command's; and under `set -euo pipefail` a bare `$( )`
aborts *after* the assignment landed).

- **Baselines** — set a new `AIT_SETUP_BASELINE_UNVERIFIED=1` instead of leaving
  an empty baseline that reads as "nothing was dirty".
- **Both commit functions** — refuse. If `AIT_SETUP_BASELINE_UNVERIFIED=1`, or
  their own list probe failed, `warn` that the dirty state could not be read and
  that framework files were **not** committed, name the manual recovery
  (`git add` / `git commit`, or `./ait git` for the data branch), and `return`
  before staging anything. Setup's own files staying uncommitted is recoverable
  by re-running `ait setup`; committing a colleague's work is not.

Note `AIT_SETUP_BASELINE_ARMED` stays `1` today even when all three probes fail,
so the "baseline not armed" warning at ~:3690 never fires. That is part of the
defect — the new flag is what makes the unverified case visible.

## A9b — the bootstrap VERSION probe (~:3647 and ~:3763)

```bash
    ! git -C "$project_dir" ls-files --error-unmatch -- .aitask-scripts/VERSION &>/dev/null
```

`&>/dev/null` conflates "not tracked" with "git is broken"; both read as
**bootstrap ⇒ empty baseline ⇒ commit-all**, the same sweep. Measured in a
scratch repo: `--error-unmatch` exits **1** for an untracked path and **128**
for a real error, so the two are separable.

The probe appears **twice** (the snapshot, and the non-interactive
blast-radius warning). Extract one helper rather than fixing it in place:

```bash
# 0 = tracked, 1 = genuinely untracked (bootstrap), 2 = unverified.
_ait_framework_version_tracked() {
    local rc=0
    git -C "$1" ls-files --error-unmatch -- .aitask-scripts/VERSION >/dev/null 2>&1 || rc=$?
    case $rc in 0) return 0 ;; 1) return 1 ;; *) return 2 ;; esac
}
```

rc 1 keeps today's commit-all behavior and its blast-radius warning; rc 2 sets
`AIT_SETUP_BASELINE_UNVERIFIED=1` and refuses.

`install.sh:1012` carries the same shape. It is **out of scope** (the sweep is
`.aitask-scripts/`), but note it in the Final Implementation Notes so it is not
lost.

## Call-site table (required by the parent's shared contract)

Enumerate all four `_ait_list_framework_changes` callers and both VERSION-probe
sites, state each disposition on "unverified", and ship a test asserting the
file's actual call sites equal the table.

## Verification

Drive the functions directly through the existing `--source-only` seam
(`aitask_setup.sh:4488`), as `tests/test_setup_git.sh` already does.

- **Discriminating fixture:** Test 21's shape — foreign **unstaged** *and*
  foreign **staged** framework edits present before the snapshot — under a
  `PATH` `git` shim that fails only `ls-files --modified`.
- **Precondition asserted** in the test *and* its control: without the shim the
  baseline is **non-empty and names those files**, i.e. protection would
  otherwise work, so the only variable is the failed probe.
- **Fail-closed:** setup refuses, warns that the dirty state is unverified, and
  **the foreign edits are still uncommitted and still staged** afterwards.
- **Negative control** against a probe-only mutant restoring `|| true`: the
  foreign files land in the framework commit. Follow
  `tests/test_fold_mark.sh::install_prefix_amend_probe` (verify the substitution
  landed; assert the rest survived).
- **A9b** gets its own shim returning **128** from `ls-files --error-unmatch`,
  plus a permit test that a genuinely untracked VERSION (rc 1) still takes the
  bootstrap commit-all path with its blast-radius warning. Both directions —
  otherwise the fix could turn every bootstrap into a refusal.
- **Permit direction stays green:** Tests 20 (bootstrap commit-all), 21
  (baseline protection), 22 and 26 (ordering) unchanged.

```bash
bash tests/test_setup_git.sh
bash tests/test_setup_metadata_commit_scope.sh
bash tests/test_data_branch_setup.sh
bash tests/test_no_unscoped_task_commit.sh
shellcheck .aitask-scripts/aitask_setup.sh
```

Shellcheck baseline: `aitask_setup.sh` carries pre-existing SC2015 / SC2034 /
SC2129 / SC2295 notes. New code must add none.
