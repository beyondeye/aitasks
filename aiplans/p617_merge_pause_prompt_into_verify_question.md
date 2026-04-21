---
Task: t617_merge_pause_prompt_into_verify_question.md
Worktree: (none — working on current branch per profile `fast`)
Branch: main
Base branch: main
---

# Plan — t617: Merge pause prompt into verify question

## Context

Currently, the manual-verification main loop in
`.claude/skills/task-workflow/manual-verification.md` issues **two**
consecutive `AskUserQuestion` calls per checklist item:

1. **Pause prompt** (step 2, sub-step 2): "Verify this item" vs
   "Stop here, continue later".
2. **Verify prompt** (step 2, sub-step 3): Pass / Fail /
   Skip (with reason) / Defer.

This doubles the interaction count for every item. Task 617 asks to
collapse them into one prompt per item. `AskUserQuestion.options` caps
at 4 explicit options (+ UI-added "Other" free text), so five first-class
options aren't representable.

**User's chosen approach (refinement of option 3 from the task
description):** keep the four existing verify options explicit, and
detect **abort keywords** in the "Other" free-text answer to trigger the
pause/abort branch. The prompt text includes a hint telling the user they
can type `abort` (or similar) to pause without archiving.

This preserves the current Skip-with-reason UX (explicit option →
follow-up reason prompt) and only changes how Abort is reached: an
implicit free-text path instead of a dedicated prompt layer.

## Scope

**Only file to modify:** `.claude/skills/task-workflow/manual-verification.md`.

**Verified no mirrors exist:** `find .gemini .agents .opencode -name
"manual-verification*"` returns nothing. Per CLAUDE.md "WORKING ON SKILLS"
section, Claude Code is the source of truth; if `.gemini/`, `.agents/`,
or `.opencode/` later grow a `task-workflow/` skill tree, a follow-up
task should mirror this change — but nothing to mirror today.

**No scripts touched.** `aitask_verification_parse.sh` already accepts the
pass/fail/skip/defer transitions; Abort is a pure SKILL.md control-flow
branch (no `set` call).

## Changes to `.claude/skills/task-workflow/manual-verification.md`

### Section 2 ("Main loop — iterate pending and deferred items")

Replace the current 5 sub-steps (`1. Render`, `2. Pause prompt`,
`3. Verify prompt`, `4. Handle the answer`, `5. Move to next item`) with
4 sub-steps that merge the pause path into the verify prompt:

```
1. Render <text> to the user as context (prefix with the index, e.g.,
   `Item 3: …`).

2. Use `AskUserQuestion` to collect the verification outcome for the
   item. The four explicit options mirror the former verify prompt;
   Abort is reachable via the UI-added "Other" free-text field and is
   advertised in the question hint.

   - Question: "Item <idx>: <text>

     Select Pass / Fail / Skip / Defer, or type in Other — ask a
     question, give an instruction, or say you want to pause (e.g.,
     'abort', 'stop for today'). Asking to pause leaves the current
     item and any remaining items unchanged with no commit."
   - Header: "Verify"
   - Options:
     - "Pass" (description: "This check passed")
     - "Fail" (description: "This check failed — create a follow-up bug task")
     - "Skip (with reason)" (description: "Not applicable / cannot verify — record a reason")
     - "Defer" (description: "Postpone until later; task will not archive while any item is deferred")

3. Handle the answer:

   **Pass:** (unchanged)
     ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> pass

   **Fail:** (unchanged — `aitask_verification_followup.sh` + ORIGIN_AMBIGUOUS handling)

   **Skip (with reason):** (unchanged — follow-up AskUserQuestion for reason, then
     ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> skip --note "<reason>")

   **Defer:** (unchanged)
     ./.aitask-scripts/aitask_verification_parse.sh set <task_file> <idx> defer

   **Other (free-text answer):** the user typed something via "Other".
     Interpret the intent (do not rely on strict keyword matching —
     judge what the user is trying to do):
     - **If the user is asking to abort, stop, pause, or otherwise
       halt the verification loop** (examples: "abort", "stop",
       "pause", "I need to stop now", "quit for today", "pause and
       come back tomorrow") → execute the **Abort branch** below.
     - **Otherwise** → treat the typed text as a normal user request
       and handle it like any in-conversation message. Examples:
       - A question about the item ("what does this check mean?") →
         answer it, then re-prompt the same item.
       - A request to investigate something before deciding ("can you
         run the tests first?") → perform the request, then re-prompt
         the same item.
       - A correction or new instruction → apply it, then re-prompt
         the same item.

       After handling, always loop back to sub-step 2 for the **same**
       item (the index does not advance until a terminal outcome —
       Pass / Fail / Skip / Defer / Abort — is recorded).

   **Abort branch** (same terminal semantics as the removed "Stop here,
     continue later" path):
     - Do NOT call `aitask_verification_parse.sh set` — the current
       item is left in its existing state (still `pending` or still
       `defer`).
     - Skip the remaining items in the loop.
     - Skip step 3 (post-loop checkpoint) and step 4 (commit
       verification state) entirely — no state has changed, so no
       commit is warranted.
     - Inform the user: "Task t<task_id> paused at item <idx>.
       Re-pick with `/aitask-pick <task_id>`."
     - End the workflow. The task stays `Implementing` and the lock
       remains held (same end state as the "Stop without archiving"
       branch in step 3 — only the message differs).

4. Move to the next pending/deferred item.
```

### What is removed

- The current sub-step 2 block (the "Verify this item / Stop here,
  continue later" `AskUserQuestion`, including its full "Stop here"
  handler).

### What is preserved (verbatim)

- Pre-loop check (section 1).
- Post-loop checkpoint (section 3 — `DEFER > 0` "Archive with carry-over
  / Stop without archiving" prompt).
- Commit verification state (section 4).
- Hand off to Step 9 (section 5).
- All script invocations and their outputs.

## Implementation Notes

- **Abort detection is intent-based, not keyword-based.** The LLM
  running the skill reads the free-text answer and decides whether the
  user is asking to pause the loop or is saying something else. This is
  more forgiving than a fixed keyword list (handles "stop for today",
  "I need to pause", "quit and resume tomorrow") and lets unrelated
  messages pass through to normal conversation handling without
  triggering an accidental abort.

- **Non-abort Other text is handled as a normal user message.** If the
  user asks a question or gives a new instruction via "Other", the
  skill responds in-conversation and then re-prompts the same item.
  The index only advances when a terminal outcome is recorded
  (Pass / Fail / Skip / Defer / Abort). This matches how code-agent
  skills handle free-text user input elsewhere.

- **Skip-with-reason stays explicit.** Users who want to record a skip
  note must select the "Skip (with reason)" option; the follow-up
  reason prompt is unchanged. This avoids the ambiguity of "did the
  user type 'N/A' because they meant skip-with-reason or because they
  wanted something else?"

- **No execution-profile key needed.** The change is a pure UX
  collapse, not an opt-in behavior. Per CLAUDE.md's "execution-profile
  keys vs. guard variables" guidance: neither lever applies — control
  flow is unconditional.

## Verification

Manual smoke-test scenarios (run `/aitask-pick` on a task with
`issue_type: manual_verification` and at least two pending items):

1. **Pass path:** Select "Pass" on item 1 → item 1 annotated `pass`, loop
   advances to item 2.
2. **Fail path:** Select "Fail" → follow-up task created via
   `aitask_verification_followup.sh`, item 1 annotated `fail`.
3. **Skip path:** Select "Skip (with reason)" → follow-up reason
   `AskUserQuestion` appears, reason saved via
   `set <idx> skip --note "<reason>"`.
4. **Defer path:** Select "Defer" → item 1 annotated `defer`, loop
   advances.
5. **Abort via direct keyword:** Type `abort` in Other on item 1 → no
   `set` call, loop ends, user sees "Task t\<id\> paused at item 1.";
   re-run `/aitask-pick <id>` resumes from item 1 unchanged.
6. **Abort via phrased intent:** Type `stop for today`, `I need to
   pause`, `quit and resume tomorrow`, `Abort!` — each should hit the
   Abort branch (intent-based, not keyword-based).
7. **Question via Other:** Type `what does this item mean?` on item 1 →
   skill answers the question in conversation, then re-prompts the same
   item. No state change.
8. **Instruction via Other:** Type `run the tests first` → skill
   performs the action, then re-prompts the same item. No state change.
9. **Defer post-loop path still works:** After setting at least one
   `Defer`, complete remaining items → section-3 post-loop checkpoint
   fires with "Archive with carry-over / Stop without archiving" (this
   path is unchanged).

## Step 9 (Post-Implementation)

Refer to `.claude/skills/task-workflow/SKILL.md` Step 9. Because
`create_worktree: false` (from profile `fast`), no branch/worktree
cleanup is needed — merge step is skipped. Archive via
`./.aitask-scripts/aitask_archive.sh 617`; the task's `issue` field is
empty so no issue-update prompts. Push via `./ait git push`.
