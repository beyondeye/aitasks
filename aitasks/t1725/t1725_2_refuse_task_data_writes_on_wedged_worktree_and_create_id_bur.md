---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
implemented_with: claudecode/opus5
created_at: 2026-09-07 16:37
updated_at: 2026-09-08 23:10
---

## Context

Parent t1725, findings 6 and 7 / acceptance criteria 4 and 5. Independent of the
other children (`--no-sibling-dep`).

**Finding 6.** When the data worktree is mid-rebase the checked-out task file is
origin's version, not the branch tip. On 2026-09-07 the rebase had stopped *before*
replaying t1717's own three commits, so the checked-out t1717 file was the stale
`status: Ready` version with no `active_gates` / `assigned_to`; the agent then wrote
its risk-gate result onto **that** file. Had it been committed, t1717 would have
flipped back to `Ready` and lost its materialized gates. No writer checks the state
of the worktree before `sed`-ing.

**Finding 7.** `ait create --batch --commit` writes the task file and then commits;
when the commit fails (the wedge, an index lock, …) the script dies under `set -e`,
the file stays on disk, and the caller retries — each retry claims a fresh id from
the atomic counter. t1722, t1723 and t1724 are byte-identical apart from timestamps.

**Scope decision (recorded in the parent plan):** the general "writer carries its
last-known base SHA" contract is not attempted — it would be a new field on every
writer. The wedge is the one production-reachable way the checked-out base differs
from what the writer last committed, and refusing there is the AC's "refused, not
applied blind".

## Key files

- `.aitask-scripts/lib/task_utils.sh` — add `assert_task_data_writable()`;
  `_data_wedge_state()` is added by sibling t1725_1 (if that has not landed, add it
  here — same name and contract — and t1725_1 reuses it); `assert_data_worktree_clean`
  (~291) is the message template
- `.aitask-scripts/aitask_update.sh` — `run_batch_mode` (~1818, before
  `resolve_task_file`), `run_interactive_mode` (~1589)
- `.aitask-scripts/aitask_create.sh` — the `--batch --commit` branch (~2193: before
  `acquire_child_lock` / `claim_unique_parent_id`), `finalize_draft` (~817), the
  interactive commit path (~2050); commit sites at ~867/905/907/2062/2240/2242/2270
- `.aitask-scripts/lib/ledger_block.sh` — covers `aitask_gate.sh` ledger appends and
  `aitask_note.sh`
- `.aitask-scripts/aitask_archive.sh`, `.aitask-scripts/aitask_plan_externalize.sh`
- `tests/test_task_git.sh` ~868 (planting `rebase-merge`),
  `tests/test_create_silent_stdout.sh` (bare remote + claim-id scaffold)

## Notes for sibling tasks

- **t1599_4** (Implementing) owns commit *scoping* in `aitask_create.sh` /
  `aitask_update.sh` (which paths each commit carries). This task adds a *pre-write
  guard* and a *commit-failure branch* — different concern, no shared lines. If both
  land near each other, rebase on the other's commit rather than merging by hand.

## Implementation plan

### Pre-phase (risk mitigation `writer_entry_point_table`) — before adding any guard call

1. [writer_entry_point_table] Write `tests/test_task_data_writer_guard.sh` as a
   **table**: one row per task-data writer script run against the planted-wedge
   fixture — `aitask_update.sh --batch <id> --priority low`,
   `aitask_create.sh --batch --commit --name x …`, `aitask_note.sh <id> --from t1 --text x`,
   `aitask_gate.sh record …` (whatever the ledger-append verb is in `aitask_gate.sh`),
   `aitask_archive.sh …`, `aitask_plan_externalize.sh <id> …` — each asserting a
   non-zero exit, the guard's message, and unchanged file bytes (md5 before/after);
   plus one row per **exempt** read-only script (`aitask_ls.sh`,
   `aitask_query_files.sh resolve <id>`, `aitask_lock.sh --check <id>`) asserting it
   still runs under the wedge. The table is the audit record: a writer missing from
   it is the hole. Enumerate candidates with
   `grep -ln 'sed_inplace\|>> *"\$\|write_task_file\|mv ' .aitask-scripts/*.sh` and
   record the audited-but-not-guarded ones (metadata-only / read-only) in the plan.
   The rows fail until step 3 lands — commit them together with it.

### Main steps

2. `task_utils.sh`: `assert_task_data_writable()` — returns 0 when
   `AIT_GIT_SKIP_STATE_CHECK=1` (the documented bypass, same as the git guard); when
   `_data_wedge_state` is non-empty, `die` with:
   "Data worktree (.aitask-data) is mid-<state>: the checked-out task files are not
   the branch tip, so writing now would land on stale content. If a sync is running
   right now, retry in a few seconds. Otherwise: ./ait git rebase --abort (discards
   only the partially replayed remote commits; your committed work stays) or resolve
   and ./ait git rebase --continue. './ait git-health' shows the full state."
   No-op in legacy mode when no data git-dir exists? **No** — legacy mode still has
   a git-dir; the helper falls back to `git rev-parse --git-dir`.
3. Call it at every writer entry from the table (step 1): `aitask_update.sh`
   (`run_batch_mode` before `resolve_task_file`, and `run_interactive_mode`),
   `aitask_create.sh` (`--batch --commit` branch **before** `acquire_child_lock` /
   `claim_unique_parent_id`; `finalize_draft`; the interactive commit path),
   `lib/ledger_block.sh` (the append entry), `aitask_archive.sh`,
   `aitask_plan_externalize.sh`. Do **not** guard draft creation in `aitasks/new/`
   (no id is claimed, nothing is committed).
4. `aitask_create.sh` commit failure **after** the file is written: do not `die`.
   Wrap `task_git add … && task_git commit …` (both the parent and the child branch;
   release the child lock first on the child branch); on failure keep the file,
   print the path on stdout exactly as on success (the `--silent` contract is "the
   path, nothing else"), and warn on stderr: "task file written but NOT committed
   (<first non-blank git line>) — it will be swept into the next sync's auto-commit
   under its own task id; do not re-run create". Skip `run_auto_merge_if_needed` on
   that branch. Exit 0.
5. `shellcheck` the touched scripts.

## Verification

`tests/test_task_data_writer_guard.sh` (table from the pre-phase, plus):
- **F6 reproduction:** local commit sets `status: Implementing` + `active_gates`;
  plant the wedge with the checked-out file at the stale `Ready` version →
  `aitask_update.sh --batch <id> --risk-code-health low` exits non-zero, the message
  names retry / abort, file bytes unchanged, nothing committed.
- **negative control:** the same update on a clean worktree succeeds.
- **F7, wedge:** `aitask_create.sh --batch --commit …` exits non-zero **before**
  claiming — `aitask_claim_id.sh --peek` identical before and after, no file written.
- **F7, commit failure:** plant `index.lock` in the data git-dir → create prints the
  path, exit 0, stderr carries "NOT committed", `--peek` advanced by exactly one;
  remove the lock, run `aitask_sync.sh --batch` → the file is committed under
  `ait: Auto-commit t<id> task data before sync` (owner derivable). A second create
  is never needed — pinned by the peek delta.
Run: `bash tests/test_task_data_writer_guard.sh`, `bash tests/test_create_silent_stdout.sh`,
`bash tests/test_task_git.sh`, `bash tests/test_update_check.sh`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1725_1** id=2026-09-08T09:47:12Z.1b468190e3f5bae4e0e26ebd from=t1725_1 from_verified=yes at=2026-09-08T09:47:12Z base=92650b0938449d14d76d8a13eba121b99a770f9f base_branch=main dirty=yes host=omg16
>
> | `_data_wedge_state()` now EXISTS — do not re-add it.
> | 
> | t1725_1 landed it in `.aitask-scripts/lib/task_utils.sh` with the name and
> | contract your plan assumed, so your step 2 can call it directly:
> | 
> | - `_data_wedge_state()` — first in-progress git state blocking task-data writes,
> |   or empty when clean. Always returns 0. Reports **all six**
> |   `AIT_GIT_INPROGRESS_STATES`, which is what your "mid-<state>" message needs for
> |   merge / cherry-pick / revert / bisect, not just the two rebase states.
> | - `_data_wedge_gitdir()` — the git-dir it reads, if you need it directly. It
> |   resolves by `ait_data_mode`, so legacy mode falls back to
> |   `git rev-parse --git-dir` while branch mode never does. Your plan's note that
> |   "legacy mode still has a git-dir; the helper falls back to
> |   `git rev-parse --git-dir`" is satisfied by this function.
> | - Both delegate to a new internal `_ait_inprogress_state_at <gitdir>`, which is
> |   also now used by `ait_data_inprogress_state` and `assert_data_worktree_clean`.
> |   If you touch that loop, you are touching all three readers.
> | 
> | Two things that may affect your plan:
> | 
> | 1. `assert_data_worktree_clean`'s die message gained a sentence — "'--abort'
> |    below discards only the partially replayed remote commits; your own committed
> |    work stays on the branch." Your `assert_task_data_writable` message was
> |    specified to carry the same clause; check the two read consistently rather
> |    than diverging in wording.
> | 
> | 2. `task_utils.sh` now sources `lib/stale_lock.sh` (for a data-worktree pull
> |    mutex). `tests/lib/test_scaffold.sh` already copied that lib, and its comment
> |    now records the new dependency — relevant if you add scaffolded tests.
> | 
> | Advisory only: verify against the current tree before relying on any of it.

> **👁 note:read** id=2026-09-08T09:59:56Z.5ab3dfda470edc5de83e6e60 by=t1725_2 at=2026-09-08T09:59:56Z mode=explicit ids=2026-09-08T09:47:12Z.1b468190e3f5bae4e0e26ebd

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-08T20:10:29Z status=pass attempt=1 type=human
