# Manual Verification Procedure

This procedure is the interactive checklist runner that `/aitask-pick` dispatches to when a picked task has `issue_type: manual_verification`. It is referenced from `SKILL.md` Step 3 (Check 3) and replaces Steps 6–8 for manual-verification tasks. Steps 4 (ownership) and 5 (worktree) still run before dispatch.

**Input:**
- `task_file` (string, required) — path to the picked task file (e.g., `aitasks/t571/t571_7_manual_verification_structured_brainstorming.md`)
- `task_id` (string, required) — task identifier (e.g., `571_7`)
- `task_name` (string, required) — filename stem, used for archive hand-off
- `active_profile` (object/null) — loaded execution profile from the calling skill

**Output:** Returns control to `SKILL.md` Step 9 (Post-Implementation) when all items are terminal, or ends the workflow early when the user chooses "Stop without archiving" while deferred items remain.

## Procedure

### 1. Pre-loop check — ensure the task has a checklist

```bash
./.aitask-scripts/aitask_verification_parse.sh summary <task_file>
```

Parse the output for `TOTAL:<N>`.

- **If `TOTAL > 0`:** proceed to the main loop.
- **If `TOTAL:0`:** the task has no `## Verification Checklist` items yet. Use `AskUserQuestion`:
  - Question: "Task has no `## Verification Checklist` items. Seed from the plan's `## Verification` section, or abort?"
  - Header: "Checklist"
  - Options:
    - "Seed from plan" (description: "Extract the bullet list under the plan's `## Verification` H2 and seed the task")
    - "Abort" (description: "Stop the workflow and revert task status")

  **If "Seed from plan":**
  1. Locate the plan file. Prefer the active plan at `aiplans/p<parent>/p<parent>_<child>_*.md` (for child tasks) or `aiplans/p<task_id>_*.md` (for parent tasks). Fall back to archived plans at `aiplans/archived/…` if no active plan exists.
  2. Read the plan file and extract the bullet list under the `## Verification` H2 (the contiguous block of `-` / `*` lines immediately following the heading, until the next H2 or EOF).
  3. Write each bullet (one per line, without leading `- `) to a temp file: `mktemp "${TMPDIR:-/tmp}/verify_seed_XXXXXX.txt"`.
  4. Seed the task:
     ```bash
     ./.aitask-scripts/aitask_verification_parse.sh seed <task_file> --items <tmp_file>
     ```
  5. Re-run `summary` and continue.

  **If "Abort":** execute the **Task Abort Procedure** (see `task-abort.md`) and end.

### 2. Main loop — iterate pending and deferred items

Enumerate items:

```bash
./.aitask-scripts/aitask_verification_parse.sh parse <task_file>
```

The helper emits one `ITEM:<idx>:<state>:<line>:<text>` line per item. For each item whose `<state>` is `pending` or `defer`:

1. Render `<text>` to the user as context (prefix with the index, e.g., `Item 3: …`).

2. Use `AskUserQuestion`:
   - Question: `<text>`
   - Header: "Verify"
   - Options:
     - "Pass" (description: "This check passed")
     - "Fail" (description: "This check failed — create a follow-up bug task")
     - "Skip (with reason)" (description: "Not applicable / cannot verify — record a reason")
     - "Defer" (description: "Postpone until later; task will not archive while any item is deferred")

3. Handle the answer:

   **Pass:**
   ```bash
   ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> pass
   ```

   **Fail:**
   ```bash
   ./.aitask-scripts/aitask_verification_followup.sh --from <task_id> --item <idx>
   ```
   Parse the output:
   - `FOLLOWUP_CREATED:<new_id>:<path>` — announce "Created follow-up bug task t<new_id>". The helper has already marked the item as `fail`; no extra `set` call needed.
   - `ORIGIN_AMBIGUOUS:<csv>` (exit 2) — the task has multiple candidate origins (e.g., aggregate tasks with `verifies: [a, b]`). Use `AskUserQuestion` with one option per task id in the csv:
     - Question: "Which feature task does this failure belong to?"
     - Header: "Origin"
     - Options: one per candidate (label = `t<id>`, description = task name if resolvable)

     Then re-invoke:
     ```bash
     ./.aitask-scripts/aitask_verification_followup.sh --from <task_id> --item <idx> --origin <chosen>
     ```
   - `ERROR:<msg>` (exit 1) — display the error and re-prompt the same item.

   **Skip (with reason):** Ask for the reason via `AskUserQuestion` (use "Other" for free text), then:
   ```bash
   ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> skip --note "<reason>"
   ```

   **Defer:**
   ```bash
   ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> defer
   ```

4. Move to the next pending/deferred item.

### 3. Post-loop checkpoint

Re-run summary:

```bash
./.aitask-scripts/aitask_verification_parse.sh summary <task_file>
```

Parse the `DEFER:<K>` count.

- **If `DEFER > 0`:** Use `AskUserQuestion`:
  - Question: "Some verification items were deferred (K=<count>). How would you like to proceed?"
  - Header: "Defer"
  - Options:
    - "Archive with carry-over" (description: "Archive now; a new manual-verification task is created containing only the deferred items")
    - "Stop without archiving" (description: "Leave the task Implementing; re-pick it later to continue the remaining items")

  **If "Archive with carry-over":** set the internal flag `use_deferred_carryover = true` so Step 9 calls the archive script with `--with-deferred-carryover`. Proceed to step 4.

  **If "Stop without archiving":** end the workflow. The task stays `Implementing` and the lock remains held so only this user can resume it. Inform the user: "Task t<task_id> left Implementing with <K> deferred items. Re-pick later with `/aitask-pick <task_id>`."

- **If `DEFER = 0`:** proceed to step 4 (standard archival).

### 4. Commit verification state

Before handing off to Step 9, commit the annotated task file so the verification record is durable:

```bash
./ait git add aitasks/
./ait git commit -m "ait: Record verification state for t<task_id>"
```

### 5. Hand off to Step 9

Return to `SKILL.md` Step 9 (Post-Implementation). Step 9 will invoke the archive script:

- If `use_deferred_carryover` was set in step 3:
  ```bash
  ./.aitask-scripts/aitask_archive.sh --with-deferred-carryover <task_id>
  ```
  The script creates a carry-over task with the remaining deferred items before archiving the primary.
- Otherwise, Step 9 runs the standard `./.aitask-scripts/aitask_archive.sh <task_id>` as usual.

Satisfaction Feedback (Step 9b) runs normally after archival.
