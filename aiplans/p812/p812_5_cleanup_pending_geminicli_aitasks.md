---
Task: t812_5_cleanup_pending_geminicli_aitasks.md
Parent Task: aitasks/t812_remove_gemini_support.md
Sibling Tasks: aitasks/t812/t812_1_*.md, aitasks/t812/t812_2_*.md, aitasks/t812/t812_3_*.md, aitasks/t812/t812_4_*.md
Archived Sibling Plans: aiplans/archived/p812/p812_1_*.md, p812_2_*.md, p812_3_*.md, p812_4_*.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified: []
---

# Plan: Cleanup pending geminicli-related aitasks (t812_5)

## Context

Final child of t812. After children 1–4 land, four pending backlog
tasks targeting geminicli-specific behavior need disposition:

- `aitasks/t343_geminicli_support_bug_planning_step_is_skipped.md`
- `aitasks/t344_seed_execution_permission_for_geminicli.md`
- `aitasks/t345_identifying_model_id_in_gemini.md`
- `aitasks/t401/t401_3_verify_detection_geminicli.md`

## Suggested dispositions

| Task | Suggested | Reason |
|------|-----------|--------|
| t343 | Close as obsolete | geminicli-specific workflow bug |
| t344 | Close as obsolete | agy uses sandboxed exec, no seed-exec-permission concern |
| t345 | Re-evaluate; close OR create new child of t814 | Model-id detection may re-apply to agy |
| t401_3 | Close as obsolete (child) | Note disposition in parent t401 |

## Step-by-step

For each pending task:

1. Read the task file to understand original intent.
2. Decide: close-as-obsolete OR migrate-to-t814.
3. **Close as obsolete:**
   ```bash
   # Append a brief obsolescence note to the task body
   # (use Edit tool to append to the file body)
   ./.aitask-scripts/aitask_update.sh --batch <task_num> \
     --status Done
   ./.aitask-scripts/aitask_archive.sh <task_num>
   ```
4. **Migrate to t814:** do NOT rename in place. After t814 exists,
   create a fresh child of t814 with the relevant content. Then
   close the original as obsolete with a pointer to the new task.
5. **For t401_3 (child task):** also update parent t401's
   `children_to_implement` list to drop t401_3, add a note in
   t401's body explaining the disposition.
6. Commit each disposition via `./ait git commit`.

## Verification

1. None of t343, t344, t345, t401_3 appear in `ait board` /
   `aitask_ls.sh -v` as Ready.
2. The four files are archived (or migrated to t814 child).
3. `grep -rn 'geminicli' aitasks/ --include='*.md'` returns only
   sibling-task files (`t812*`, `t813*`, `t814*`) and archived
   files.

## Step 9 (Post-Implementation)

Standard archival. Final Implementation Notes **must** include the
`### For t814 (add-agy): inverse instructions` subsection (even
though this child is primarily admin work — t814's planner may
benefit from the migrate/close decisions).

## Final Implementation Notes (template)

- **Actual work done:** …
- **Deviations from plan:** …
- **Issues encountered:** …
- **Key decisions:** …
- **Upstream defects identified:** None (or list)
- **Notes for sibling tasks:** …

### For t814 (add-agy): inverse instructions

- **Migrated-to-t814 task IDs:** (list any that genuinely
  transferred, with new t814 child ID and one-line summary).
- **Closed as obsolete:** (list of IDs + reason — e.g., "t344:
  agy uses sandboxed exec, no seed permission concern").
- **Hidden coupling discovered:** anything about the original task
  framing that informs agy's design (e.g., t345's model-id surface
  concerns may inform how agy exposes its model id).
