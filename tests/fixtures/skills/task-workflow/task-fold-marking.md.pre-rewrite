# Task Fold Marking (reference)

Marking tasks as folded (updating `folded_tasks` on the primary, setting `status: Folded` and `folded_into` on each folded task, handling transitive folds, removing folded child tasks from their parent's `children_to_implement`, and committing) is handled by `.aitask-scripts/aitask_fold_mark.sh`. See that script for the canonical implementation.

## Usage

```bash
./.aitask-scripts/aitask_fold_mark.sh [--no-transitive] [--commit-mode fresh|amend|none] <primary_id> <folded_id1> <folded_id2> ...
```

**Commit modes:**
- `fresh` (default) — stage `aitasks/` and create a new commit `ait: Fold tasks into t<primary>: merge t<id1>, t<id2>, ...`. Emits `COMMITTED:<short_hash>`.
- `amend` — stage `aitasks/` and `git commit --amend --no-edit` (folds the marking into the previous commit, used by callers that just created or updated the primary). Emits `AMENDED`.
- `none` — skip commit (the caller stages and commits). Emits `NO_COMMIT`.

**Transitive handling:** by default, if a folded task already has its own `folded_tasks`, those transitive IDs are appended to the primary's list and their `folded_into` is re-pointed at the primary. Pass `--no-transitive` to disable.

**Child task cleanup:** for each folded ID in `<parent>_<child>` format, the script automatically removes the child from its parent's `children_to_implement` list (via `aitask_update.sh --remove-child`).

## Structured Output

The script emits one line per action: `PRIMARY_UPDATED:<primary_id>`, `FOLDED:<id>`, `CHILD_REMOVED:<parent>_<child>`, `TRANSITIVE:<id>`, and one of `COMMITTED:<hash>` / `AMENDED` / `NO_COMMIT`.
