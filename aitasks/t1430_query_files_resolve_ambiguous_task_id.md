---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [bash_scripts]
gates: [risk_evaluated]
followup_kind: upstream_defect
created_at: 2026-08-05 15:52
updated_at: 2026-08-13 23:07
---

## Origin

Spawned from t1377_1 during Step 8b review.

## Upstream defect

- `aitask_query_files.sh:402-407` — `cmd_resolve` emits a multi-line
  `TASK_FILE:<paths>` when a task number matches two or more files, instead of
  refusing an ambiguous id; a caller parsing one line silently gets a two-line
  value.

The relevant code:

```bash
files=$(ls "$TASK_DIR"/t"${num}"_*.md 2>/dev/null || true)
if [[ -z "$files" ]]; then
    echo "NOT_FOUND"
    return
fi
echo "TASK_FILE:$files"
```

`ls` returns one path per line, so two matching files produce:

```
TASK_FILE:aitasks/t42_one.md
aitasks/t42_two.md
```

The second line carries no `TASK_FILE:` prefix, so a consumer that reads the
first line gets one of two candidates with no signal that the id was ambiguous,
and a consumer that greps the prefix silently drops the second path. `validate_num`
already guards the id *shape*, so this is purely the multiple-match case.

## Diagnostic context

Surfaced while building the headless board-column seam (t1377_1). That task
needed a task-id → file resolution rule for a value arriving from a CLI, and
`cmd_resolve` was the obvious precedent to copy. On inspection it turned out to
mishandle the duplicate-match case, so `lib/board_columns.py:_resolve_task`
deliberately does **not** follow it — it refuses a distinct `ambiguous_task_id`
reason and writes nothing, with a comment naming this as a bug to avoid rather
than a precedent. `tests/test_board_columns_seam.py` and
`tests/test_board_column_cli.sh` both cover the ambiguous case for that module.

Duplicate `t<N>_*.md` files are not supposed to exist, but nothing enforces it —
they can arise from a partially-applied rename, a bad merge, or a manual copy.
The failure is silent in exactly those situations.

## Suggested fix

Count the matches in `cmd_resolve` and emit a distinct `AMBIGUOUS:<paths>` (or
`NOT_FOUND`-style refusal) rather than a malformed `TASK_FILE:` record. Audit the
callers of `resolve` first — `aitask-pick`'s Step 0b parses `TASK_FILE:` and
would need to handle the new line. Consider the same check for the sibling
lookups (`child-file`, `archived-task`) if they share the shape.
