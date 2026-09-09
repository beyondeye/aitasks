---
Task: t1747_4_setup_dirty_baseline_probe.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1747_4 — `ait setup`'s dirty baseline must not read "unverified" as "clean"

## Context

Audit rows A9 + A9b (see `aidocs/framework/failopen_git_probes.md`) — the second
of the two candidates the t1747 task body names. The consequence here is not a
lost commit but a **stolen** one: another session's uncommitted work committed
under `ait: Add aitask framework`.

## Implementation

### A9 — `_ait_list_framework_changes` (~:3584-3597)

The function is consumed in **two opposite polarities**, and only one is safe:

| call | ~line | polarity | probe-failure effect |
|---|---|---|---|
| baseline, main tree | 3654 | **subtrahend** | empty baseline ⇒ nothing subtracted ⇒ `commit_framework_files` **sweeps foreign work**. Fail-OPEN |
| baseline, data tree | 3666 | **subtrahend** | same; worse, since that function's comment says concurrent sessions "routinely have in-progress work" there |
| change list, main | 3707 | minuend | empty ⇒ nothing committed, reported as `success "All framework files already committed"`. False success |
| change list, data | 3865 | minuend | same |
| post-commit `still_untracked` | 3804 | display | informational — leave as-is |

**Fix.** Give the helper a real exit status. The **trailing** `|| true` on the
`printf | sed | sort | grep -Ev` pipeline is load-bearing and stays — `grep -Ev`
exits 1 on a legitimately empty result. Only the three `git` captures change:

```bash
    local untracked modified staged probe_rc=0
    untracked="$(git -C "$workdir" ls-files --others --exclude-standard -- "$@" 2>/dev/null)" || probe_rc=1
    modified="$(git -C "$workdir" ls-files --modified -- "$@" 2>/dev/null)"          || probe_rc=1
    staged="$(git -C "$workdir" diff --cached --name-only -- "$@" 2>/dev/null)"      || probe_rc=1
    printf '%s\n%s\n%s\n' "$untracked" "$modified" "$staged" \
        | sed '/^$/d' | sort -u | grep -Ev "$exclude_re" || true
    (( probe_rc == 0 )) || return 2
```

Every one of the four call sites absorbs it with `|| rc=$?`, `local rc=0`
declared on its **own line** first.

- **Baselines** — set `AIT_SETUP_BASELINE_UNVERIFIED=1` instead of arming an
  empty baseline that reads as "nothing was dirty".
- **Both commit functions** — refuse. On `AIT_SETUP_BASELINE_UNVERIFIED=1`, or
  on their own list probe failing: `warn` that the dirty state could not be read
  and that framework files were **not** committed, name the manual recovery
  (`git add` / `git commit`; `./ait git` for the data branch), and `return`
  before staging anything.

  **Why refuse rather than commit.** This is the opposite disposition from
  `task_git_commit_scoped`, and deliberately so: there the unsafe outcome is a
  lost commit, so it commits anyway; here the unsafe outcome is committing
  someone else's work, so it stops. Setup's own files staying uncommitted is
  recoverable by re-running `ait setup`.

`AIT_SETUP_BASELINE_ARMED` stays `1` today even when all three probes fail, so
the "baseline not armed" warning (~:3690) never fires. That is part of the
defect — the new flag is what makes the unverified case visible. Do **not**
overload `ARMED` to mean both things; a third state needs its own name.

### A9b — the bootstrap VERSION probe (~:3647 and ~:3763)

`&>/dev/null` conflates "not tracked" with "git is broken"; both read as
**bootstrap ⇒ empty baseline ⇒ commit-all**, the same sweep. Measured in a
scratch repo: `ls-files --error-unmatch` exits **1** for an untracked path and
**128** for a real error.

The probe appears **twice** (the snapshot, and the non-interactive blast-radius
warning), so extract it rather than fixing it in place:

```bash
# 0 = tracked, 1 = genuinely untracked (bootstrap), 2 = unverified.
_ait_framework_version_tracked() {
    local rc=0
    git -C "$1" ls-files --error-unmatch -- .aitask-scripts/VERSION >/dev/null 2>&1 || rc=$?
    case $rc in 0) return 0 ;; 1) return 1 ;; *) return 2 ;; esac
}
```

rc 1 keeps today's commit-all behaviour **and its blast-radius warning**; rc 2
sets `AIT_SETUP_BASELINE_UNVERIFIED=1` and refuses.

`install.sh:1012` carries the same shape. **Out of scope** (the sweep is
`.aitask-scripts/`) — record it in the Final Implementation Notes so it is not
lost.

## Call-site table

All four `_ait_list_framework_changes` callers and both VERSION-probe sites,
each with its disposition on unverified, plus a test asserting the file's actual
call sites equal the table.

## Verification

Drive the functions directly through the existing `--source-only` seam
(`aitask_setup.sh:4488`), as `tests/test_setup_git.sh` already does.

- **Discriminating fixture:** Test 21's shape — a foreign **unstaged** edit *and*
  a foreign **staged** edit to tracked framework files, both present before the
  snapshot — under a `PATH` `git` shim failing only `ls-files --modified`. The
  staged one is load-bearing: it is invisible to `--others` and `--modified`
  alike, which is why the `diff --cached` term exists.
- **Precondition**, asserted in the test *and* its control: without the shim the
  baseline is **non-empty and names those files** — i.e. protection would
  otherwise work — so the only variable is the failed probe.
- **Fail-closed:** setup refuses, warns that the dirty state is unverified, and
  **the foreign edits are still uncommitted and still staged** afterwards
  (assert the porcelain status, not just the commit contents).
- **Negative control** against a probe-only mutant restoring `|| true`: the
  foreign files land in the framework commit. Follow
  `tests/test_fold_mark.sh::install_prefix_amend_probe` — verify the substitution
  landed, and assert the surrounding baseline machinery survived.
- **A9b** gets its own shim returning **128** from `ls-files --error-unmatch`,
  **plus** a permit test that a genuinely untracked VERSION (rc 1) still takes
  the bootstrap commit-all path with its blast-radius warning. Both directions —
  otherwise the fix silently turns every fresh install into a refusal.
- **Permit direction stays green:** Tests 20, 21, 22, 26 unchanged.

```bash
bash tests/test_setup_git.sh
bash tests/test_setup_metadata_commit_scope.sh
bash tests/test_data_branch_setup.sh
bash tests/test_no_unscoped_task_commit.sh
shellcheck .aitask-scripts/aitask_setup.sh
```

Shellcheck baseline: pre-existing SC2015 / SC2034 / SC2129 / SC2295 notes. New
code must add none.

## Risk

### Code-health risk: low
- One helper plus four absorbing callers, and one extracted predicate replacing
  a duplicated inline probe. · severity: low · → mitigation: none needed.

### Goal-achievement risk: medium
- A refusal in `commit_framework_files` means a fresh `ait setup` can end with
  framework files uncommitted — visible, but a worse first-run experience if it
  fires spuriously. · severity: medium · → mitigation: none needed as a task —
  the A9b permit test pins that the *bootstrap* path (the common fresh-install
  case) is untouched, and refusal requires an actual git failure, not merely an
  empty result.
