---
Task: t1747_2_automerge_rebase_skip_probe.md
Parent Task: aitasks/t1747_sweep_failopen_git_probes.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1747_2 — `ait_automerge_advance` must not authorise `rebase --skip` on an unread probe

## Context

Audit rows A1 + A2 (see `aidocs/framework/failopen_git_probes.md`). The
highest-severity site in the t1747 sweep: the fail-open outcome is a **discarded
commit**, on the framework's hottest path — both `pull --rebase` drivers reach
it (`ait sync` and every pick/push via `lib/task_utils.sh::_task_pull_rebase`).

The t1747 task body points at `aitask_sync.sh::_rebase_advance`, which no longer
exists: `66da94134` (t1727) extracted it to `lib/task_automerge.sh`.

## Implementation

### 1. `lib/task_automerge.sh::ait_automerge_advance` (~:197-208)

```bash
    local unresolved="" u_rc=0
    unresolved="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || u_rc=$?
    # A failed probe must never authorise `rebase --skip` — skipping DISCARDS the
    # replayed commit. "Unverified" is not "nothing unresolved".
    # Rule + dispositions: aidocs/framework/failopen_git_probes.md
    if (( u_rc == 0 )) && [[ -z "$unresolved" ]] && _ait_data_git rebase --skip &>/dev/null; then
        return 0
    fi
    return 1
```

`local unresolved="" u_rc=0` on its **own line** before the capture: under
`set -euo pipefail`, `local x="$(…)" || rc=$?` captures `local`'s status, not the
command's.

The comment **points at the doc**; it does not restate the rule. That is the
t1747_1 convention.

### 2. Decide A2 (`_ait_automerge_conflicted_now`, ~:212) explicitly

Two consumers, opposite risk profiles — record the decision either way:

| consumer | today | after step 1 |
|---|---|---|
| `ait_automerge_rebase_loop` **entry** (~:236) | failed probe ⇒ empty ⇒ `ait_automerge_files ""` returns 0 ⇒ falls into `ait_automerge_advance` | that call now refuses ⇒ loop re-probes ⇒ `return 2` ⇒ caller aborts |
| **post-advance** (~:272) | failed probe ⇒ empty ⇒ `return 2` ⇒ abort | unchanged; already fail-closed |

Both funnel to the safe abort once step 1 lands, so a second refusal here may be
redundant. Prefer the honest helper anyway **if** it costs nothing: an explicit
"unverified" is easier to reason about than "wrong for a reason that happens to
be caught downstream". Whichever is chosen, write the reasoning into the
function's comment — a future reader must not have to re-derive it.

### 3. Call-site table

Enumerate every consumer of both helpers with its disposition on "unverified",
and ship a test asserting the file's actual call sites equal the table, so a new
consumer cannot be added bare. (Parent contract; A10 in t1747_3 is the case that
proves why.)

## Why `return 1` is safe — verified at all three call sites

| caller | behaviour on `advance` ⇒ 1 |
|---|---|
| `ait_automerge_rebase_loop` (~:263) | re-probes; probe fails again ⇒ empty ⇒ `return 2` |
| `aitask_sync.sh:1002` (interactive) | `warn "Rebase continue failed. Aborting rebase."` + `rebase --abort` + `return 1` |
| `lib/task_utils.sh:1216` (workflow pull) | rc 1 and rc 2 both fall through to `ait_rebase_abort_if_ours`, which **verifies the abort landed** |

Every route ends in an abort that restores the worktree and keeps local commits.
`tests/test_sync_branch_mode_automerge.sh` Test 9 already pins the rc-2 surface
(`ERROR:rebase_continue_failed`, `assert_no_rebase_wedge`).

## Verification

Extend `tests/test_sync_branch_mode_automerge.sh`; reuse its seams —
`setup_branch_mode_repos`, `setup_two_body_conflicts`, `assert_no_rebase_wedge`,
and the argv-keyed shim shape of `install_failing_advance_shim`.

### The discriminating fixture

A rebase state where `rebase --skip` **would otherwise have succeeded**, so the
test proves a failed probe does not authorise the commit-discarding path — not
merely that something failed.

1. **Preferred (natural):** both sides make the *same* edit, so the replayed
   patch becomes empty, `rebase --continue` fails with "nothing to commit", and
   the `--skip` fallback legitimately applies.
2. **Fallback (injected):** if (1) does not reliably reach the skip branch, fail
   **only** `rebase --continue` through the argv shim. That is
   production-reachable — it is exactly the state the `--skip` fallback exists
   for — so the case remains a real one, not a synthetic impossibility.

Say in the Implementation Record which was used and why.

### Preconditions, asserted in the test AND its control

- **(a)** unshimmed, the advance takes the skip branch and **succeeds** — so the
  fixed code's refusal can only come from the probe;
- **(b)** under the probe shim, `diff --name-only --diff-filter=U` exits
  non-zero.

Without (a) the test could satisfy its assertion through an unrelated failure.

### Assertions

| direction | assertion |
|---|---|
| fail-closed | run reports `ERROR:rebase_continue_failed`, exits non-zero, `assert_no_rebase_wedge`, and **the commit `--skip` would have discarded is still reachable** (`git log` on the data branch names it) |
| negative control | against a mutant restoring `\|\| true`: the same fixture takes `rebase --skip` and that commit is **gone** — via `assert_defect_present` |
| permit | Tests 1-9 unchanged; in particular a legitimate empty-patch skip still completes |

The mutant installer follows `tests/test_fold_mark.sh::install_prefix_amend_probe`:
regress **only** the probe, `sys.exit(1)` on a stale anchor, re-grep to prove the
substitution landed, and assert `ait_automerge_advance` and its `rebase --skip`
call survived — otherwise the control observes "no guard" rather than "fail-open
guard".

```bash
bash tests/test_sync_branch_mode_automerge.sh
bash tests/test_sync.sh
shellcheck .aitask-scripts/lib/task_automerge.sh   # baseline: clean apart from SC1091
```

## Risk

### Code-health risk: low
- One function, one added status capture; the refusal path is the file's
  existing rc-1 contract. · severity: low · → mitigation: none needed.

### Goal-achievement risk: low
- The natural empty-patch fixture may not reach the skip branch, forcing the
  injected variant. · severity: low · → mitigation: none needed — the injected
  variant is production-reachable and the plan pre-authorises it, so this
  changes the fixture, not the claim.
