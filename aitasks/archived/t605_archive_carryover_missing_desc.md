---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_archive, aitask_verification]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-21 07:58
updated_at: 2026-04-21 08:48
completed_at: 2026-04-21 08:48
---

## Bug

`.aitask-scripts/aitask_archive.sh`'s `create_carryover_task()` invokes `aitask_create.sh --batch --commit --silent --name <x> --type manual_verification --priority medium --effort low [--verifies <y>]` without supplying `--desc` or `--desc-file`.

`aitask_create.sh --batch` now aborts this call:

```
Error: Batch mode requires --desc or --desc-file
```

As a result, archiving a `manual_verification` task with `--with-deferred-carryover` fails with exit 1 and no carry-over task is created.

## Reproduction

1. Pick any `manual_verification` task with at least one deferred item.
2. At the post-loop checkpoint choose "Archive with carry-over".
3. `./.aitask-scripts/aitask_archive.sh --with-deferred-carryover <id>` exits 1 with the error above.

Encountered live during t597_6 archival, 2026-04-21.

## Hotfix already applied

Inline patch added to `create_carryover_task()` that synthesises a stock description:

```bash
local orig_id
orig_id=$(echo "$orig_basename" | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*/\1/')
local carryover_desc="Carry-over of deferred manual-verification items from t${orig_id}. Re-pick this task to continue the remaining checklist."
# …
create_args=(--batch --commit --silent
    --name "$carryover_name"
    --desc "$carryover_desc"
    --type manual_verification
    --priority medium --effort low)
```

This unblocked the t597_6 archive. This task tracks that the hotfix is adequate — specifically, whether the stock description should instead include a rendered list of the deferred items or a pointer back to the original task file.

## Second bug — `aitask_create.sh --silent` pollutes stdout with git-commit summary

Found while fixing the first bug. When `aitask_create.sh --batch --commit --silent` is run, the internal `task_git commit` call writes git's default output (e.g. `[aitask-data abc123] ait: Add task t609: ...\n 1 file changed, 12 insertions(+)\n create mode 100644 ...`) to stdout **before** the silent-mode filename echo. A caller that captures `$(./.aitask-scripts/aitask_create.sh --silent ...)` receives this multi-line blob instead of the filename, breaking any `[[ -f "$captured" ]]` or similar test.

This is how the archive's `create_carryover_task()` silently fails even after the first hotfix lands: `--desc` is now supplied, but `$new_file` captures the git noise, so the `-f` check fails and we die with "Carry-over task creation failed".

### Hotfix applied

In `aitask_create.sh`, guarded the three `task_git commit` calls that fire during `--batch --commit` (parent creation, child creation, and draft finalization) to use `--quiet` with stdout redirected to stderr when silent mode is active:

```bash
if [[ "$BATCH_SILENT" == true ]]; then
    task_git commit --quiet -m "ait: Add task ${task_id}: ${humanized_name}" >&2
else
    task_git commit -m "ait: Add task ${task_id}: ${humanized_name}"
fi
```

(Also in `finalize_draft()`'s sibling path.)

### Acceptance (both bugs)

- `aitask_archive.sh --with-deferred-carryover <id>` succeeds without manual intervention for any `manual_verification` task with deferred items.
- Carry-over task body includes either (a) the stock description currently used, or (b) a richer description that enumerates the deferred checklist items and references the source task.
- `aitask_create.sh --batch --commit --silent` prints **only** the created filename on stdout. Git's commit summary goes to stderr (or is suppressed via `--quiet`).
- Tests:
  - `tests/test_archive_carryover.sh` — create a manual_verification task with one deferred item, archive with `--with-deferred-carryover`, assert a carry-over task was created and seeded.
  - `tests/test_create_silent_stdout.sh` — run `aitask_create.sh --batch --commit --silent`, assert stdout is a single line that is exactly an existing file path.
