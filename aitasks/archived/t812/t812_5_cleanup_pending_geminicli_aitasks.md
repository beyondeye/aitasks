---
priority: low
effort: low
depends: [t812_4]
issue_type: chore
status: Done
labels: [geminicli, backlog]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-26 12:07
updated_at: 2026-05-28 08:49
completed_at: 2026-05-28 08:49
---

## Context

Fifth (final) child of t812. After the framework no longer supports
geminicli (children 1–4), four pending aitasks in the backlog that
target geminicli-specific behavior become obsolete or need to migrate.
This child surveys each and applies a disposition.

## Pending tasks to dispose of

- `aitasks/t343_geminicli_support_bug_planning_step_is_skipped.md`
- `aitasks/t344_seed_execution_permission_for_geminicli.md`
- `aitasks/t345_identifying_model_id_in_gemini.md`
- `aitasks/t401/t401_3_verify_detection_geminicli.md`

## Suggested dispositions (final call during implementation)

| Task | Suggested | Reason |
|------|-----------|--------|
| t343 | Close as not-applicable | Bug refers to geminicli-specific workflow. |
| t344 | Close as not-applicable | agy uses sandboxed execution; no seed exec-permission step exists. |
| t345 | Close OR migrate to t814 child | Model-id detection may reapply to agy; if it does, create a new child of t814 instead of migrating in place. |
| t401_3 | Close as obsolete | Child task; note disposition in parent t401. |

## Implementation plan

For each pending task:
1. Read the task file to understand the original intent.
2. Decide: close-as-obsolete (most cases) or migrate-to-t814 (rare,
   only if the concern genuinely transfers to agy).
3. Apply via:
   ```bash
   # Close as obsolete (mark Done with a brief explanation in body)
   ./.aitask-scripts/aitask_update.sh --batch <task_num> \
     --status Done
   # Then archive immediately since there's no implementation to do:
   ./.aitask-scripts/aitask_archive.sh <task_num>
   ```
   For migrate-to-t814: do NOT rename in place; create a fresh child
   of t814 (after t814 exists) and close the original as obsolete
   with a pointer to the new task.
4. For t401_3 (child task), update parent t401's
   `children_to_implement` list to drop t401_3, and add a note in
   t401's body explaining the disposition.
5. Commit each disposition via `./ait git commit`.

## Verification

1. After all dispositions, none of the four tasks appear in
   `ait board` / `aitask_ls.sh -v` as Ready.
2. The four task files are either archived
   (`aitasks/archived/...`) or moved to a t814 child.
3. `grep -rn 'geminicli\|gemini-cli' aitasks/` returns only sibling
   tasks (`t812*`, `t813*`, `t814*`) and archived files.

## Final implementation notes — REQUIRED subsection

Include a top-level subsection titled exactly:

```
### For t814 (add-agy): inverse instructions
```

Contents:
- **Migrated-to-t814 task IDs:** list any of t343/t344/t345/t401_3
  that genuinely transferred. For each, give the new t814 child
  ID and a one-line summary of the concern.
- **Closed as obsolete (no migration needed):** list of task IDs
  that were closed without transfer, with the reason
  (geminicli-specific concern, not applicable to agy's sandboxed
  model, etc.).
- **Hidden coupling discovered during disposition:** anything about
  the original task framing that informed agy's design (e.g., "t345
  flagged that geminicli's model-id surface was inconsistent; agy
  should expose model id via `agy --version` or equivalent").
