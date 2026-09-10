---
priority: high
effort: medium
depends: [t1747_1]
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1733
implemented_with: claudecode/opus5
created_at: 2026-09-09 11:12
updated_at: 2026-09-10 12:48
---

## Context

Child of t1747 (see `aiplans/p1747_sweep_failopen_git_probes.md` for the full
audit; the rule and the canonical fix shape live in
`aidocs/framework/failopen_git_probes.md`, landed by t1747_1).

Covers **audit rows A1 and A2** — the highest-severity site in the sweep,
because the fail-open outcome is a discarded commit, on the hottest path in the
framework.

**Note the task body of t1747 has a stale reference:** `aitask_sync.sh::_rebase_advance`
no longer exists. Commit `66da94134` (t1727) extracted it to
`lib/task_automerge.sh`, where it is now reachable from **two** drivers — `ait sync`
*and* every pick/push via `lib/task_utils.sh::_task_pull_rebase`.

## The defect

`lib/task_automerge.sh::ait_automerge_advance` (~:197-208):

```bash
    local unresolved
    unresolved=$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null || true)
    if [[ -z "$unresolved" ]] && _ait_data_git rebase --skip &>/dev/null; then
        return 0
    fi
    return 1
```

A failed probe (index.lock contention, an unreadable `.git`, a swallowed
`_ait_data_git` failure) yields `""`, which reads as "no unresolved files — this
is an empty patch", and runs **`git rebase --skip`, permanently dropping the
commit being replayed**.

A2 is the sibling `_ait_automerge_conflicted_now` (~:212), same `|| true` shape.
Its **post-advance** consumer (`ait_automerge_rebase_loop`, the `return 2`
branch) is already fail-closed. Its **loop-entry** consumer compounds into A1: a
failed probe yields an empty conflict set, `ait_automerge_files ""` iterates
nothing and returns 0, and control falls straight into `ait_automerge_advance`.

## Fix

```bash
    local unresolved="" u_rc=0
    unresolved="$(_ait_data_git diff --name-only --diff-filter=U 2>/dev/null)" || u_rc=$?
    if (( u_rc == 0 )) && [[ -z "$unresolved" ]] && _ait_data_git rebase --skip &>/dev/null; then
        return 0
    fi
    return 1
```

`local unresolved="" u_rc=0` on its **own line** before the capture — under
`set -euo pipefail`, `local x="$(…)" || rc=$?` captures `local`'s status, not the
command's.

### `return 1` is verified safe at all three call sites

| caller | on `advance` returning 1 |
|---|---|
| `lib/task_automerge.sh::ait_automerge_rebase_loop` (~:263) | re-probes; the probe fails again ⇒ empty ⇒ `return 2` ⇒ caller aborts |
| `aitask_sync.sh:1002` (interactive resolution) | `warn "Rebase continue failed. Aborting rebase."` + `rebase --abort` + `return 1` |
| `lib/task_utils.sh:1216` (workflow pull) | rc 1 and rc 2 both fall through to the verified abort (`ait_rebase_abort_if_ours`) |

Every route ends in an abort that restores the worktree and keeps local commits.
`tests/test_sync_branch_mode_automerge.sh` Test 9 already pins the rc-2 outcome
(`ERROR:rebase_continue_failed`, no wedge).

### Call-site table (required by the parent's shared contract)

Enumerate every consumer of both helpers, state each one's disposition on
"unverified", and ship a test asserting the file's actual call sites equal the
table — so a new consumer cannot be added bare. Decide explicitly whether A2's
loop-entry use needs its own refusal or is adequately covered once A1 refuses;
record the reasoning either way.

## Verification

- **Discriminating fixture:** a rebase state where `rebase --skip` **would
  otherwise have succeeded** — the empty-patch case the fallback exists for — so
  the test proves a failed probe does not authorise the commit-discarding path,
  not merely that something failed. Preferred construction is natural (both
  sides make the *same* edit, so the merge leaves nothing to commit); if that
  does not reliably reach the skip branch, inject it through the argv-keyed
  `PATH` shim seam by failing **only** `rebase --continue`, which is a
  production-reachable state (it is exactly when the code falls through to
  `--skip`).
- **Preconditions asserted before the run**, in the test *and* its control:
  (a) unshimmed, the advance takes the skip branch and succeeds — so the fixed
  code's refusal can only come from the probe; (b) under the probe shim,
  `diff --diff-filter=U` exits non-zero.
- **Fail-closed assertions:** the run reports `ERROR:rebase_continue_failed`,
  exits non-zero, leaves no rebase wedge (`assert_no_rebase_wedge`), and **the
  commit `--skip` would have discarded is still reachable**.
- **Negative control** against a mutant restoring the `|| true` shape: the same
  fixture takes `rebase --skip` and the commit is **gone**. Follow
  `tests/test_fold_mark.sh::install_prefix_amend_probe` — regress **only** the
  probe, fail loudly on a stale anchor, verify the substitution landed, and
  assert the rest of the function survived. Assert via `assert_defect_present`.
- **Permit direction stays green:** existing Tests 1-9 unchanged, in particular
  the legitimate empty-patch skip.

Reuse the existing seams in `tests/test_sync_branch_mode_automerge.sh`:
`setup_branch_mode_repos`, `setup_two_body_conflicts`, `assert_no_rebase_wedge`,
`install_failing_advance_shim`.

```bash
bash tests/test_sync_branch_mode_automerge.sh
bash tests/test_sync.sh
shellcheck .aitask-scripts/lib/task_automerge.sh
```

Shellcheck baseline: `lib/task_automerge.sh` is clean apart from SC1091. New
code must add none.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1747_1** id=2026-09-09T13:33:04Z.51b85cf7fa38a375e3b54def from=t1747_1 from_verified=yes at=2026-09-09T13:33:04Z base=e7e9fcb9a5672cd47728cc209d124f265c7c08f7 base_branch=main dirty=yes host=omg16
>
> | The plan's call-site table cites `lib/task_utils.sh:1216` as the third consumer
> | ("workflow pull — rc 1 and rc 2 both fall through to the verified abort
> | `ait_rebase_abort_if_ours`"). Verified against HEAD e7e9fcb9a: that line is a
> | comment inside the `_ait_load_automerge` lazy-loader block, not a consumer.
> | 
> | The claim itself holds — the real site is
> | `lib/task_utils.sh::_task_pull_rebase_cleanup`:
> | 
> |   :1344  if _ait_load_automerge; then
> |   :1346      ait_automerge_rebase_loop || loop_rc=$?
> |   :1352-1354  # rc 1 (conflicts we cannot merge) and rc 2 (advance failed for a
> |              # non-conflict reason) both fall through to the abort
> |   :1359  verdict="$(ait_rebase_abort_if_ours _ait_data_git ...)"
> | 
> | So the argument is confirmed in-tree; only the pointer is wrong. Worth fixing
> | before the table is used as the safety evidence for `return 1`, since a reader
> | checking that third call site today lands on nothing.
> | 
> | Also: `aidocs/framework/failopen_git_probes.md` now exists (t1747_1) and is the
> | canonical anchor for the rule, the fix shape and the Group A row A1/A2 you own.
> | Point at it rather than restating the rule.

> **👁 note:read** id=2026-09-09T13:43:32Z.3afd8b35b44dc9705d32ddbb by=t1747_2 at=2026-09-09T13:43:32Z mode=explicit ids=2026-09-09T13:33:04Z.51b85cf7fa38a375e3b54def

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T09:48:09Z status=pass attempt=1 type=human
