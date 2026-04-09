---
priority: high
effort: low
depends: []
issue_type: bug
status: Ready
labels: [cli]
created_at: 2026-04-09 08:53
updated_at: 2026-04-09 08:53
---

In aitask_update.sh line 1353-1354, the rename logic constructs the new path as:

```bash
local new_filename="t${BATCH_TASK_NUM}_${sanitized_name}.md"
final_path="$TASK_DIR/$new_filename"
```

For a child task where BATCH_TASK_NUM is e.g. `47_1`, this produces `final_path="aitasks/t47_1_new_name.md"` — placing the file in the root `aitasks/` directory instead of preserving the child subdirectory `aitasks/t47/t47_1_new_name.md`.

The fix should use `dirname "$file_path"` instead of `$TASK_DIR` to preserve the original directory:

```bash
local parent_dir
parent_dir=$(dirname "$file_path")
final_path="$parent_dir/$new_filename"
```

Discovered during t500 planning.
