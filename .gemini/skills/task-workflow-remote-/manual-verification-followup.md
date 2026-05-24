# Manual Verification Follow-up Procedure

Runs from task-workflow **Step 8c**, after the "Commit changes" branch has committed code and plan files. Offers the user a chance to queue a standalone manual-verification task that will be picked after this task archives — covering behavior only a human can validate (TUI flows, live agent launches, on-disk artifact inspection).

## Input context

From the caller (SKILL.md Step 8c):
- `task_file` — path to the current task file.
- `task_id` — task identifier (e.g. `42` or `42_3`).
- `task_slug` — filename stem without the `t<id>_` prefix (e.g. `add_login`).
- `is_child` — boolean.
- `active_profile` — loaded execution profile (may be null).
- `parent_id` — parent task number if `is_child`, else null.

## Procedure

**⚠️ NON-SKIPPABLE — Auto mode and 'work without stopping' directives do NOT bypass the Step 8c prompt.**

The AskUserQuestion in step 4 below is the workflow gate that decides whether
a standalone manual-verification follow-up task is created. The following do
NOT cover this prompt:
- Auto mode / 'work without stopping' system-injected directives.
- Generic user instructions to 'be brief' or 'don't ask'.
- Profile keys other than the one named below.

The only valid skips are:
- The profile key `manual_verification_followup_mode: never` (handled by
  step 1 below before the prompt is reached), or
- The user explicitly typing a decision in chat before the prompt fires.

### 1. Profile check



Profile 'remote' sets `manual_verification_followup_mode: never`. Display:

> "Profile 'remote': skipping manual-verification follow-up prompt."

Return to the caller (which proceeds to Step 9).



### 2. Skip conditions

Independent of profile — these reflect structural reasons the prompt is meaningless. Return to the caller (proceed to Step 9) if any of these are true:

- `is_child` is `true` — child tasks are covered by the aggregate-sibling flow in the parent's planning phase.
- The task's `issue_type` is `manual_verification` — these tasks don't need follow-ups.
- An aggregate manual-verification sibling was created during Step 6 child-task flow (detect by checking whether any sibling in `aitasks/t<parent_id>/` has `issue_type: manual_verification` when children were just created in this session).

### 3. Discovery — assemble candidate checklist items

Scan the following sources in order and write de-duplicated bullets to a temp file `<tmp_checklist>`:

1. **Task body `## Verification Steps`** — read `<task_file>`; extract bullet lines under the `## Verification Steps` H2 (if present). Strip the leading `- ` / `* `.
2. **Plan `## Verification`** — resolve the plan file via `./.aitask-scripts/aitask_query_files.sh plan-file <task_id>`; extract bullet lines under `## Verification` (if present).
3. **Plan `## Final Implementation Notes`** — same plan file; extract bullets under the `- **Deviations from plan:**` and `- **Issues encountered:**` fields. These often describe behaviors worth verifying by hand.
4. **Diff scan of Step 8 commits** — run `git log --oneline --grep "(t<task_id>)" -n 20` to list commits just made for this task; for each, run `git show --name-only --format= <hash>` and collect the unique file set. For each file matching a known interactive surface, emit a `TODO: verify <file> end-to-end in tmux` bullet:
   - Interactive surfaces: files under `.aitask-scripts/board/`, files whose names contain `tui`, `brainstorm`, `codebrowser`, `monitor`, `stats`, `walker`, `switcher`; `.py` files that `import textual`; shell scripts that call `fzf` or `gum` (grep the file).

If all four sources yield zero candidates, write a single stub line: `TODO: define verification for t<task_id>`.

### 4. User review

Display the assembled candidate bullets to the user as a numbered list (output them as plain text before the prompt, not inside option labels).

Then use `AskUserQuestion`:
- Question: "Does this task need a manual-verification follow-up to cover behavior only a human can validate? Candidate checklist items were discovered above."
- Header: "Manual verify"
- Options:
  - "No, skip" (description: "Proceed to Step 9 without creating a follow-up")
  - "Yes, use candidates as-is" (description: "Create the follow-up with the bullets shown above")
  - "Yes, let me edit the list first" (description: "Edit the checklist file before creating the follow-up")

**If "No, skip":** Return to the caller (proceed to Step 9).

**If "Yes, let me edit the list first":** Tell the user the `<tmp_checklist>` path and ask them to edit it with the Read/Edit tools. After they confirm, re-read the file and proceed to step 5 below.

### 5. Seed the follow-up task

On either "Yes" option (after any edits):

```bash
./.aitask-scripts/aitask_create_manual_verification.sh \
  --related <task_id> \
  --name manual_verification_<task_slug>_followup \
  --verifies <task_id> \
  --items <tmp_checklist>
```

Parse the `MANUAL_VERIFICATION_CREATED:<new_id>:<path>` line and display: "Created manual-verification follow-up task t\<new_id\>."

Return to the caller (proceed to Step 9).
