---
priority: medium
effort: medium
depends: [t583_1]
issue_type: feature
status: Implementing
labels: [framework, skill, task_workflow, verification]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 08:29
updated_at: 2026-04-19 15:24
---

## Context

Fifth child of t583. Implements the **archival gate** that prevents `aitask_archive.sh` from archiving a manual-verification task while any items are still unchecked. Also implements the **carry-over** path: when archiving with only deferred items remaining, create a new manual-verification task containing just those deferred items.

Depends on t583_1 (uses the `terminal_only` subcommand as the gate primitive).

## Key Files to Modify

- `.aitask-scripts/aitask_archive.sh` — add pre-archive gate in `main()`; add `--with-deferred-carryover` flag.

## Reference Files for Patterns

- `.aitask-scripts/aitask_archive.sh` `main()` around line 530-540 — dispatch point where the gate slots in.
- `.aitask-scripts/aitask_archive.sh` `archive_parent()` at line 170, `archive_child()` at line 347 — functions the gate precedes.
- `.aitask-scripts/aitask_create.sh --batch` for the carry-over task creation.

## Implementation Plan

1. **Pre-archive gate (in `main()` before dispatching):**
   ```bash
   # After parse_args, before the parent/child branch
   local task_file
   task_file=$(resolve_task_id_to_file "$TASK_NUM") || die "Task not found"
   local issue_type
   issue_type=$(read_frontmatter_field "$task_file" issue_type)
   
   if [[ "$issue_type" == "manual_verification" ]]; then
       if ! ./.aitask-scripts/aitask_verification_parse.sh terminal_only "$task_file" >/tmp/verify_check.$$; then
           local has_pending has_defer
           has_pending=$(grep -c '^PENDING:' /tmp/verify_check.$$ || echo 0)
           has_defer=$(grep -c '^DEFERRED:' /tmp/verify_check.$$ || echo 0)
           
           if [[ "$has_pending" -gt 0 ]]; then
               cat /tmp/verify_check.$$
               echo "VERIFICATION_PENDING: cannot archive until all items are terminal"
               exit 2
           fi
           
           if [[ "$has_defer" -gt 0 && "$WITH_DEFERRED_CARRYOVER" != "true" ]]; then
               cat /tmp/verify_check.$$
               echo "VERIFICATION_DEFERRED: use --with-deferred-carryover to archive with carry-over"
               exit 2
           fi
       fi
   fi
   ```

2. **New flag `--with-deferred-carryover`:**
   - Parse into `WITH_DEFERRED_CARRYOVER=true`.
   - Before archival proceeds (inside the gate block above), when only deferred items remain:
     - Read the deferred items via `aitask_verification_parse.sh parse "$task_file" | awk -F: '$3 == "defer"'`.
     - Build a new checklist temp file with just those item texts.
     - Extract `verifies:` from the original task.
     - Call:
       ```
       ./.aitask-scripts/aitask_create_manual_verification.sh \
           --name "<orig_name>_deferred_carryover" \
           --verifies "<orig_verifies>" \
           --items <tmp_checklist>
       ```
       (Uses the seeder from t583_7 — but t583_7 depends on t583_2 and t583_6, not on this task. If the seeder is not yet available at implementation time of t583_5, fall back to calling `aitask_create.sh --batch` directly with `--type manual_verification` and seed the checklist via `aitask_verification_parse.sh seed` after creation. t583_7 then refactors the direct call into the seeder.)
     - Capture the new task ID; print `CARRYOVER_CREATED:<new_id>:<path>`.

3. **Testing exit codes:**
   - `VERIFICATION_PENDING` → exit 2 (user must finish verification).
   - `VERIFICATION_DEFERRED` (without flag) → exit 2 (user must add flag or finish deferred items).
   - Success with `--with-deferred-carryover` → normal archive flow + `CARRYOVER_CREATED` line.

4. **Help text update:** Document the new flag and the new exit code 2 semantics in `show_help()`.

## Verification Steps

- Manual-verification task with 1 pending + 1 pass → `aitask_archive.sh <id>` exits 2 with `VERIFICATION_PENDING:1`.
- Task with 0 pending + 1 defer + 1 pass → exits 2 with `VERIFICATION_DEFERRED:1`.
- Same task with `--with-deferred-carryover` → archives successfully; new task created with just the deferred item; original's `verifies:` preserved on the new one.
- Non-manual-verification tasks: gate is no-op, existing behavior preserved.

## Step 9 reminder

Commit: `feature: Add archival gate and carry-over for manual-verification (t583_5)`.
