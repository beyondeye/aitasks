---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, aitask_pick, claudeskills]
created_at: 2026-04-27 11:41
updated_at: 2026-04-27 11:41
---

Update task-workflow Step 8 so that when implementation revealed an upstream
defect during diagnosis, the agent must proactively offer a follow-up
aitask for the upstream root cause as part of the user-review prompt.

## Origin

Spawned from t664 (review claude memories). Encodes the rule from the
auto-memory `feedback_offer_upstream_followup_proactively.md`, captured
after t660 (brainstorm TUI silently quitting on plan import). The
diagnostic revealed a stale `crew-brainstorm-<N>` git branch left over
by a worktree-prune ordering bug in `aitask_brainstorm_delete.sh:109-111`.
The plan only added a recovery modal for the symptom; the user had to
explicitly ask for both (a) a "Delete branch & retry" affordance and (b)
acknowledgment of the upstream `delete` bug. They rated the skill 1-2
(Poor) because the agent made them push for the upstream follow-up
rather than offering it.

## Rule (verbatim from memory)

> When a bug investigation reveals that the failure was *seeded* by an
> upstream defect (e.g. a previous tool that should have cleaned up state
> but didn't), do not just file the upstream bug as a "noted, separate
> task" line in the plan file. **Proactively offer to create a follow-up
> aitask for it during Step 8 review.**
>
> **Why:** On t660 the immediate symptom was the brainstorm TUI silently
> quitting on plan import; the diagnostic revealed a stale
> `crew-brainstorm-<N>` git branch left over by `ait brainstorm delete`
> (worktree-prune ordering bug in `aitask_brainstorm_delete.sh:109-111`).
> The plan only added a recovery modal for the symptom; the user had to
> explicitly ask both for (a) a "Delete branch & retry" affordance in the
> modal and (b) acknowledgment of the upstream `delete` bug. They rated
> the skill 1-2 (Poor) because the agent made them push for the upstream
> follow-up rather than offering it.
>
> **How to apply:** In Step 8 review, when a diagnosis surfaces an
> upstream defect, include in the AskUserQuestion both "commit changes"
> and an explicit follow-up question: "Want me to also file the upstream
> <X> bug as a new aitask?" Don't bury the upstream cause in plan-file
> prose — make it a discrete, opt-in offer the user can accept in one
> click. Not every investigation has an upstream root cause, but when one
> is identified and is fixable as its own task, surface it.

## Where to add

Target file: `.claude/skills/task-workflow/SKILL.md`

Section: Step 8 (User Review and Approval), in the AskUserQuestion block
that lists "Commit changes / Need more changes / Abort task".

Suggested implementation:

1. **Pre-prompt assessment (new sub-step):** Before showing the
   AskUserQuestion, the agent reflects: "During implementation, did I
   identify any upstream defect that is out of scope for this task but
   fixable as its own?" If yes, capture a one-line description and the
   suggested file/line context.

2. **Add a second AskUserQuestion (or extra option):** When an upstream
   defect was identified, after the standard "Commit changes / Need more
   changes / Abort task" prompt, show a follow-up:
   - Question: "Diagnosis surfaced an upstream <X> bug at <location>.
     Create a follow-up aitask for it?"
   - Header: "Upstream"
   - Options:
     - "Yes, create follow-up task" (description: "Spawn a new aitask
       documenting the upstream defect, with the diagnostic context")
     - "No, skip" (description: "Note in plan file only; no separate
       task")

3. **If "Yes, create follow-up task":** Use the **Batch Task Creation
   Procedure** (`task-creation-batch.md`) to create a `bug` task whose
   description includes the diagnostic context discovered during
   implementation, plus a back-reference to the current task ID.

## Implementation suggestions

- The "did I identify an upstream defect?" reflection is the
  load-bearing part — it must be expressed as an explicit numbered step
  that the agent cannot skip. Per CLAUDE.md "Skill / Workflow Authoring
  Conventions", consider this a structural step (numbered, in SKILL.md),
  not a passive note.
- Consider adding a context-variable `upstream_followup_offered`
  (boolean, default false) so the offer fires once per Step 8 invocation
  and isn't re-asked after "Need more changes" loops.
- Include the t660 example as the canonical illustration in the
  procedure text.

## Cross-agent parity follow-up

Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS", after this Claude
Code change lands, suggest follow-up tasks to mirror the change in:
- `.opencode/skills/task-workflow/SKILL.md`
- `.gemini/skills/task-workflow/SKILL.md`
- `.agents/skills/task-workflow/SKILL.md`

## Verification

- `git diff .claude/skills/task-workflow/SKILL.md` shows the new
  upstream-defect reflection step plus the conditional AskUserQuestion.
- The t660 example appears in the procedure text.
- Manual: implement a fix that touches a downstream symptom of an
  upstream issue and confirm the new prompt fires.
