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

### 2. Main loop — render checklist, then ask about the current item

This is a re-entrant outer loop: every state mutation (single-option answer or
parsed batch update) loops back to the top so the rendered checklist always
reflects the current state and the "current item" is always the first remaining
`pending` or `defer` entry.

1. **Enumerate items:**

   ```bash
   ./.aitask-scripts/aitask_verification_parse.sh parse <task_file>
   ```

   The helper emits one `ITEM:<idx>:<state>:<line>:<text>` line per item.

2. **Exit condition:** if no item is in state `pending` or `defer`, leave the
   loop and proceed to step 3 (post-loop checkpoint).

3. **Render the FULL NUMBERED CHECKLIST** as plain text — one line per item,
   with a short state marker so the user always has the overview. Example:

   ```
   Verification checklist (5 items):
     1. ✓ pass    Open the brainstorm TUI and confirm the left pane renders
     2. ✓ pass    Ctrl+B opens the brainstorm view
     3. ⏳ pending Ctrl+N spawns a new task from the brainstorm view
     4. ⏳ pending Agent spawn lands in a fresh tmux window
     5. ⏸ defer   Verify tmux session reuse logic
   ```

   Canonical state markers (use these consistently):

   | state   | marker    |
   |---------|-----------|
   | pending | `⏳ pending` |
   | pass    | `✓ pass`   |
   | fail    | `✗ fail`   |
   | skip    | `⊘ skip`   |
   | defer   | `⏸ defer`  |

   (Plain ASCII fallbacks are acceptable when the terminal cannot render the
   unicode glyphs.)

4. **Print a one-line tip immediately after the checklist** advertising the
   Other-field batch path. This is the discovery surface for the batch path —
   keep it visible on every loop iteration; do not bury it inside the
   `AskUserQuestion` text. Example wording:

   ```
   Tip: in the Other field you can batch-resolve multiple items in one go,
   e.g. "3 pass, 4 fail, 5 skip not applicable" (verbs: pass / fail / skip / defer).
   ```

5. **Identify the CURRENT item:** the first item whose state is `pending` or
   `defer` (lowest index).

6. **Ask** — use `AskUserQuestion` scoped to the current item. The four explicit
   options are the per-item outcomes; batch updates, conversational messages,
   and the pause/abort path all flow through "Other".
   - Question: `"Item <idx>: <text>\n\nPass / Fail / Skip / Defer for this item, or use Other (see tip above)."`
   - Header: "Verify"
   - Options:
     - "Pass" (description: "This check passed")
     - "Fail" (description: "This check failed — create a follow-up bug task")
     - "Skip (with reason)" (description: "Not applicable / cannot verify — record a reason")
     - "Defer" (description: "Postpone until later; task will not archive while any item is deferred")

7. **Handle the answer.**

   **Pass / Fail / Skip / Defer (single-option choice):** apply to the CURRENT
   item using the per-state command, then loop back to sub-step 1.

   - **Pass:**
     ```bash
     ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> pass
     ```

   - **Fail:**
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

   - **Skip (with reason):** Ask for the reason via `AskUserQuestion` (use "Other" for free text), then:
     ```bash
     ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> skip --note "<reason>"
     ```

   - **Defer:**
     ```bash
     ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> defer
     ```

   **Other (free-text answer):** the user typed something via "Other". Interpret
   the intent — do not rely on a fixed keyword list; judge what the user is
   trying to do, in this priority order:

   - **(i) Pause / abort intent** — phrases like "abort", "stop", "pause", "I
     need to stop now", "quit for today", "pause and come back tomorrow" →
     execute the **Abort branch** below.

   - **(ii) Batch update** — the text is one or more entries matching the
     pattern `<idx> <verb> [args]`, separated by commas, semicolons, or
     newlines. `<verb>` is `pass | fail | skip | defer` (case-insensitive).
     `<idx>` must be a valid item index (1-based) currently in state `pending`
     or `defer`. Also accept a **shorthand single-entry form with no leading
     index** (e.g., the user types just `pass`, `skip not applicable`) — apply
     it to the current item.

     For each parsed entry, in order, run the same per-state command as the
     single-option choices above:

     | verb  | action |
     |-------|--------|
     | pass  | `./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> pass` |
     | fail  | `./.aitask-scripts/aitask_verification_followup.sh --from <task_id> --item <idx>` (handle `FOLLOWUP_CREATED` / `ORIGIN_AMBIGUOUS` / `ERROR` exactly as in the single-option Fail branch) |
     | skip  | `./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> skip --note "<rest-of-entry-text>"` (rest-of-entry-text = everything after `skip` until the next delimiter; if empty, prompt once for a reason via `AskUserQuestion`) |
     | defer | `./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> defer` |

     **Validation:** if any entry references an out-of-range index, an index
     already in a terminal state (`pass` / `fail` / `skip`), or an unknown
     verb, do NOT silently drop it. Stop processing further entries, list the
     problem entries to the user, then loop back to sub-step 1 (re-render the
     checklist and re-ask). Already-applied entries from the same batch stay
     applied — there is no rollback.

     After all valid entries are applied successfully, loop back to sub-step 1.

   - **(iii) Conversational message** — neither pause nor a batch update.
     Treat the typed text as a normal user request (answer a question about
     the item, perform a requested investigation, apply a correction, etc.).
     After handling, loop back to sub-step 6 to re-ask the **same** current
     item. The current item does not change until a terminal outcome — Pass /
     Fail / Skip / Defer / Abort — is recorded for it.

   **Abort branch** (same terminal semantics as the former "Stop here, continue later" path):
   - Do NOT call `aitask_verification_parse.sh set` — the current item is left in its existing state (still `pending` or still `defer`).
   - Skip the remaining items in the loop.
   - Skip step 3 (post-loop checkpoint) and step 4 (commit verification state) entirely — no state has changed, so no commit is warranted.
   - Inform the user: "Task t<task_id> paused at item <idx>. Re-pick with `/aitask-pick <task_id>`."
   - End the workflow. The task stays `Implementing` and the lock remains held (same end state as the "Stop without archiving" branch in step 3 — only the message differs).

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
