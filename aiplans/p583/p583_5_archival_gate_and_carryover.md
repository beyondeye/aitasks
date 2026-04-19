---
Task: t583_5_archival_gate_and_carryover.md
Parent Task: aitasks/t583_manual_verification_module_for_task_workflow.md
Sibling Tasks: aitasks/t583/t583_1_*.md .. t583_9_*.md
Archived Sibling Plans: aiplans/archived/p583/p583_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t583_5 — Archival Gate + Carry-over

## Context

Prevents `aitask_archive.sh` from archiving a manual-verification task while items are still pending. Adds `--with-deferred-carryover` flag to archive with only deferred items remaining (creates a new task holding the deferred subset).

Depends on t583_1 (uses `terminal_only` as the gate primitive).

## Files to modify

- `.aitask-scripts/aitask_archive.sh`

## Changes

**Pre-archive gate** (in `main()` after `parse_args`, before dispatching to parent/child archival ~line 530-540):

```bash
local task_file
task_file=$(resolve_task_id_to_file "$TASK_NUM") || die "Task not found"
local issue_type
issue_type=$(read_frontmatter_field "$task_file" issue_type)

if [[ "$issue_type" == "manual_verification" ]]; then
    local gate_out
    if ! gate_out=$(./.aitask-scripts/aitask_verification_parse.sh terminal_only "$task_file"); then
        if echo "$gate_out" | grep -q "^PENDING:"; then
            echo "$gate_out"
            echo "VERIFICATION_PENDING: cannot archive until all items are terminal"
            exit 2
        fi
        if echo "$gate_out" | grep -q "^DEFERRED:" && [[ "$WITH_DEFERRED_CARRYOVER" != "true" ]]; then
            echo "$gate_out"
            echo "VERIFICATION_DEFERRED: use --with-deferred-carryover to archive with carry-over"
            exit 2
        fi
    fi

    if [[ "$WITH_DEFERRED_CARRYOVER" == "true" ]]; then
        # Build carry-over task (deferred items only) before archiving
        # See carry-over block below
        create_carryover_task_for "$task_file"
    fi
fi
```

**New flag `--with-deferred-carryover`:** parse into `WITH_DEFERRED_CARRYOVER=true`; add to `parse_args` case.

**Carry-over task creation:** filter parser output for `:defer:`, build a new checklist file with those item texts, extract the original's `verifies:`, then call the seeder from t583_7 (or fall back to raw `aitask_create.sh` + `aitask_verification_parse.sh seed` if t583_7 hasn't landed yet). Print `CARRYOVER_CREATED:<new_id>:<path>`.

**Help text update:** document the new flag and exit code 2 semantics.

## Reference precedent

- `.aitask-scripts/aitask_archive.sh` `main()` ~530, `archive_parent()` ~170, `archive_child()` ~347.
- `.aitask-scripts/lib/task_utils.sh` `read_frontmatter_field()`.

## Verification

- Manual-verification task with 1 pending → exit 2 with `VERIFICATION_PENDING:1`.
- All terminal except 1 defer → exit 2 with `VERIFICATION_DEFERRED:1`.
- Same + `--with-deferred-carryover` → archives + `CARRYOVER_CREATED` line.
- Non-manual-verification task → gate is no-op (existing behavior preserved).

## Final Implementation Notes

_To be filled in during implementation._
