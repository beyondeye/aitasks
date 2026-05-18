# Task Fold Content (reference)

Building the merged description body is handled by `.aitask-scripts/aitask_fold_content.sh`. See that script for the canonical implementation.

## Usage

**Merging into an existing primary task** (aitask-fold, planning ad-hoc fold):

```bash
./.aitask-scripts/aitask_fold_content.sh <primary_task_file> <folded_file1> <folded_file2> ...
```

**Building content for a new primary task** (aitask-explore, aitask-pr-import, aitask-contribution-review):

```bash
printf '%s\n' "<description from exploration>" | \
  ./.aitask-scripts/aitask_fold_content.sh --primary-stdin <folded_file1> <folded_file2> ...
```

The script writes the merged description body to stdout in a structured format:
- Primary body preserved at the top
- `## Merged from t<N>: <name>` section for each folded task
- `## Folded Tasks` reference section at the end

Callers typically pipe the output into `aitask_update.sh --batch <id> --desc-file -` (for existing primaries) or pass it as the `description` argument to the **Batch Task Creation Procedure** (for new primaries).
