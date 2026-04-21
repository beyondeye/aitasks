---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_archive, aitask_verification]
created_at: 2026-04-21 07:58
updated_at: 2026-04-21 07:58
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

## Acceptance

- `aitask_archive.sh --with-deferred-carryover <id>` succeeds without manual intervention for any `manual_verification` task with deferred items.
- Carry-over task body includes either (a) the stock description currently used, or (b) a richer description that enumerates the deferred checklist items and references the source task.
- Add a test (`tests/test_archive_carryover.sh`) that creates a manual_verification task with one deferred item, archives with `--with-deferred-carryover`, and asserts a carry-over task was created and seeded.
