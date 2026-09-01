# Task Fold Marking (reference)

Marking tasks as folded (updating `folded_tasks` on the primary, setting `status: Folded` and `folded_into` on each folded task, handling transitive folds, removing folded child tasks from their parent's `children_to_implement`, and committing) is handled by `.aitask-scripts/aitask_fold_mark.sh`. See that script for the canonical implementation.

## Usage

```bash
./.aitask-scripts/aitask_fold_mark.sh [--no-transitive] [--commit-mode fresh|amend|none] <primary_id> <folded_id1> <folded_id2> ...
```

**Commit modes:** every mode stages only the fold's own file set — never `aitasks/` wholesale — so a dirty or pre-staged bystander is never swept in.
- `fresh` (default) — create a new commit `ait: Fold tasks into t<primary>: merge t<id1>, t<id2>, ...`. Emits `COMMITTED:<short_hash>`, or `NO_COMMIT` when those paths are verifiably unchanged.
- `amend` — `git commit --amend --no-edit` (folds the marking into the previous commit, used by callers that just created or updated the primary). Emits `AMENDED`. It **refuses** — exits non-zero and rolls the whole fold back — when HEAD is not this fold's to rewrite: it carries a path outside the fold, or it is already published on the upstream.

An unrecognised mode is rejected at argument-parse time, before any task is resolved or mutated.
- `none` — skip commit (the caller stages and commits). Emits `NO_COMMIT`.

**Transitive handling:** by default, if a folded task already has its own `folded_tasks`, those transitive IDs are appended to the primary's list and their `folded_into` is re-pointed at the primary. Pass `--no-transitive` to disable.

**Child task cleanup:** for each folded ID in `<parent>_<child>` format, the script automatically removes the child from its parent's `children_to_implement` list (via `aitask_update.sh --remove-child`).

## Structured Output

The script emits one line per action: `PRIMARY_UPDATED:<primary_id>`, `FOLDED:<id>`, `CHILD_REMOVED:<parent>:<child>`, `TRANSITIVE:<id>`, and one of `COMMITTED:<hash>` / `AMENDED` / `NO_COMMIT`.

**A record means "the commit step reached a terminal success".** The four per-action records are buffered while the mutations happen and reach stdout only on one of the commit step's three terminal *success* outcomes, flushed in emission order immediately ahead of the terminal record:

| terminal record | meaning |
|---|---|
| `COMMITTED:<hash>` | this fold's own commit was created |
| `AMENDED` | the fold was folded into the preceding commit |
| `NO_COMMIT` | no commit was created — and that is still a **success**: either `--commit-mode none` (the caller commits the mutations itself) or a verified no-op (git reports these paths unchanged) |

So `NO_COMMIT` is a valid flush outcome, not a failure, and a record does **not** imply durable git history — it means that mutation *survived* the commit step and is on disk, committed or handed to the caller to commit. Every rollback path undoes the whole fold and prints **nothing**, with the reason on stderr, so a consumer never observes progress for a transaction that was rolled back.

## The whole run is one transaction

The fold's file set is assembled and snapshotted **before the first mutation**, and an `EXIT` trap rolls back on **any** abort from that point onward — a folded ID with no task file, a failed attachment merge or rebind, a refused amend, a failed commit. So an empty record set means what it looks like: nothing landed.

The rollback restores each snapshotted path's **pre-fold state** — working-tree bytes *and* index entry, every stage, so a path in an unresolved merge round-trips — rather than restoring from `HEAD`. That distinction is load-bearing: the ad-hoc fold flow runs `aitask_fold_content.sh | aitask_update.sh --desc-file -` immediately before the marking script and does not commit, so the primary is routinely dirty (and may be staged) on entry, and an aborted fold may discard none of it.

`--commit-mode` is validated at argument-parse time, before anything is resolved or mutated, so a bad mode never starts a transaction at all.

**What this does not buy:** a signal that bypasses the `EXIT` trap (`SIGKILL`, power loss) still leaves the mutations on disk. **The exit status remains authoritative:** on a non-zero exit, check the worktree rather than reading an empty record set as proof.
