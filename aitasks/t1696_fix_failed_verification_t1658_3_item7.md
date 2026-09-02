---
priority: medium
effort: medium
depends: [t1658_1]
issue_type: bug
status: Implementing
labels: [verification, bug]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1658
followup_kind: verification_failure
created_at: 2026-09-02 18:55
updated_at: 2026-09-02 22:34
---

## Failed verification item from t1658_1

> [t1658_1] From that partial state, run `./ait sync` and confirm the branch converges (both `./ait git rev-list --count @{u}..HEAD` and `HEAD..@{u}` reach 0) with no work lost.

### Source

- **Manual-verification task:** `aitasks/t1658/t1658_3_manual_verification_data_branch_metadata_push.md` (item #7)
- **Origin feature task:** t1658_1
- **Origin archived plan:** `aiplans/archived/p1658/p1658_1_converge_local_data_branch_after_offbranch_push.md`

### Commits that introduced the failing behavior

- cb271b5a9 bug: Converge the local data branch after an off-branch metadata push (t1658_1)

### Files touched by those commits

- .agents/skills/task-workflow-remote-codex-/satisfaction-feedback.md
- .aitask-scripts/aitask_usage_update.sh
- .aitask-scripts/aitask_verified_update.sh
- .aitask-scripts/lib/task_utils.sh
- .aitask-scripts/lib/verified_update_lib.sh
- .claude/skills/task-workflow-remote-/satisfaction-feedback.md
- .claude/skills/task-workflow/satisfaction-feedback.md
- .opencode/skills/task-workflow-remote-/satisfaction-feedback.md
- tests/golden/procs/task-workflow/satisfaction-feedback-default.md
- tests/golden/procs/task-workflow/satisfaction-feedback-fast.md
- tests/golden/procs/task-workflow/satisfaction-feedback-remote.md
- tests/lib/metadata_update_fixture.sh
- tests/test_task_push.sh
- tests/test_usage_update.sh
- tests/test_verified_update.sh

### Observed behavior (recorded during t1658_3 auto-verification, 2026-09-02)

Reproduced on this checkout with three other agent sessions live.

**Setup — the partial state was forced exactly as item #6 specifies:**
`aitasks/metadata/models_claudecode.json` left locally modified, then
`aitask_usage_update.sh --agent-string claudecode/opus4_6 --skill pick`.
Item #6 passed: stdout `UPDATED_REMOTE_ONLY:claudecode/opus4_6:pick:5`, exit 3,
explanation on stderr, local edit untouched. Branch left `behind 1 / ahead 0`,
with metadata commit `759616e58` on `origin/aitask-data` only.

**Then the probe edit was reverted, leaving the genuine partial state**
(behind 1 / ahead 0, models_claudecode.json clean, four unrelated task/plan
files dirty because their tasks are locked by live sessions).

**`./ait sync` did not converge:**

```
RC=0
sync: not everything was auto-committed —
  - t1675 is locked by a LIVE session on omg16 - its files left dirty for that session to commit
  - t1677 is locked by a LIVE session on omg16 - its files left dirty for that session to commit
  - t1658_3 is locked by a LIVE session on omg16 - its files left dirty for that session to commit
  - t1686 is locked by a LIVE session on omg16 - its files left dirty for that session to commit
Warning: Sync deferred: 4 protected file(s) block the rebase; the fetch still ran.

after:  ahead @{u}..HEAD = 0   behind HEAD..@{u} = 1
merge-base --is-ancestor 759616e58 HEAD -> NO (commit still missing locally)
```

`ait sync` exits **0** while leaving the branch behind, so a caller cannot tell
recovery failed.

**`task_data_converge()` — the seam t1658_1 itself added — recovered it immediately:**

```
STATUS=fast-forwarded REASON= AHEAD=0 BEHIND=0
merge-base --is-ancestor 759616e58 HEAD -> YES
```

All four dirty foreign files were still present and byte-identical (md5 unchanged)
afterwards.

### The defect

The partial-outcome messages direct the user to a command that cannot perform the
recovery in the very situation that produces the partial outcome:

- `lib/verified_update_lib.sh:191` - "... not on the local data branch (converge: ...) - recover with './ait sync'"
- `lib/task_utils.sh:732` - "local edits to the same file(s) block the fast-forward; commit them or reconcile with './ait sync'"
- `lib/task_utils.sh:734` - "local data branch has both unpushed and unpulled commits; reconcile with './ait sync'"

`ait sync` reconciles via `pull --rebase`, which requires a clean worktree. Its
own t1599 lock protection deliberately leaves live-locked task files dirty and
then takes the `protected_dirty` deferral (`aitask_sync.sh` step 5 early exit),
so on a multi-agent box the recommended recovery is unreachable — while
`task_data_converge()`'s `fetch` + `merge --ff-only` succeeds against exactly
that state.

**Not a data-loss bug:** nothing was lost, and the next metadata update
self-heals because it calls `task_data_converge()` before committing. The defect
is the misdirecting recovery instruction (and `ait sync`'s silent exit 0), not
the convergence seam, which behaved correctly throughout.

### Suggested direction (not prescriptive)

Point the recovery hint at a path that works with a dirty shared worktree - e.g.
name the converge seam directly, or have `ait sync` run `task_data_converge()`
on its `protected_dirty` deferral path before giving up. Whatever is chosen, the
hint and the reachable recovery must agree.

### Additional surface carrying the same hint

The rendered satisfaction-feedback procedures repeat the unreachable advice on the
partial-result branch and must be updated together with the shell messages:

- `.claude/skills/task-workflow/satisfaction-feedback.md:42` and `:93`
- `.claude/skills/task-workflow-remote-/satisfaction-feedback.md:38-area` and `:87-area`
- `.agents/skills/task-workflow-remote-codex-/satisfaction-feedback.md`
- `.opencode/skills/task-workflow-remote-/satisfaction-feedback.md`
- goldens under `tests/golden/procs/task-workflow/satisfaction-feedback-*.md`

(The continue-not-abort contract in those files is correct and was verified working
in t1658_3 item 8 - only the `./ait sync` recovery wording is at issue.)

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t1658_3 item #7.
