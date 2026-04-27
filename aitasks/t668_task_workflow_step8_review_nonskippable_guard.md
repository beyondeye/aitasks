---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [task_workflow, aitask_pick, claudeskills]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-27 11:42
updated_at: 2026-04-27 12:00
---

Add explicit, prominent language to task-workflow Step 8 stating that the
AskUserQuestion review prompt ("Commit changes / Need more changes /
Abort task") is non-skippable — no execution-profile key, no auto-mode
behavior, and no shortcut may elide it.

## Origin

Spawned from t664 (review claude memories). Encodes the rule from the
auto-memory `feedback_step8_user_review_is_must.md`, captured during
t645 (Apr 26 2026) when the user explicitly flagged: "You did not allow
me to review changes, before commit." Auto mode's "minimize
interruptions / prefer assumptions for routine decisions" guidance was
misapplied — the Step 8 review is a deliberate user-checkpoint that the
SKILL.md describes as a MUST, not a routine decision.

## Rule (verbatim from memory)

> In task-workflow Step 8, surface the AskUserQuestion review prompt
> ("Commit changes / Need more changes / Abort task") to the user before
> staging or committing any implementation diff. This is non-skippable in
> interactive sessions even when the active execution profile is `fast`
> or when auto mode is on.
>
> **Why:** During task t645 (Apr 26 2026), the user explicitly flagged:
> "You did not allow me to review changes, before commit." Auto mode's
> "minimize interruptions / prefer assumptions for routine decisions"
> guidance was misapplied — the Step 8 review is a deliberate
> user-checkpoint that the SKILL.md describes as a MUST ("the user MUST
> be given the opportunity to review and test changes before any commits
> are made"), not a routine decision. Skipping it removes the user's
> last chance to test the change before it lands in git.
>
> **How to apply:** In any task-workflow run (aitask-pick, aitask-explore,
> etc.), after implementation but before any `git add` / `git commit`,
> ALWAYS call AskUserQuestion with the standard "Commit changes / Need
> more changes / Abort task" options. Auto mode and execution-profile
> shortcuts (`skip_task_confirmation`, `post_plan_action`, etc.) target
> other prompts in the flow — they do NOT cover the Step 8 review. Treat
> that AskUserQuestion as load-bearing infrastructure, not as a routine
> confirmation that auto mode can elide. The only valid skips are the
> ones the SKILL.md text itself names (e.g., a profile key with
> `commit_review: skip` if/when one exists — none today).

## Where to add

Target file: `.claude/skills/task-workflow/SKILL.md`

Section: Step 8 (User Review and Approval), at the top of the section
before "Show change summary".

Suggested implementation: a prominent **NON-SKIPPABLE** callout block,
e.g.:

```markdown
**⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this
review.**

The AskUserQuestion below is load-bearing infrastructure, not a routine
confirmation. Auto mode's "minimize interruptions / prefer assumptions
for routine decisions" guidance and execution-profile shortcuts
(`skip_task_confirmation`, `post_plan_action`, etc.) target other
prompts in the flow — they do NOT cover this review. The only valid
skips are profile keys explicitly named in this SKILL.md as covering
Step 8 review (currently: none). Skipping this prompt removes the user's
last chance to test the change before it lands in git.

This rule was added after t645, where the user flagged: "You did not
allow me to review changes, before commit."
```

The callout should be visible without scrolling — place it as the FIRST
content under the Step 8 heading, before "After implementation is
complete..." paragraph.

## Implementation suggestions

- The callout's job is to make agents reading SKILL.md (or having it
  parsed by code) trip immediately over the non-skippable rule before
  they reach the AskUserQuestion definition.
- Cross-reference Auto Mode behavior explicitly so future agents
  reading "auto mode active" reminders know this exception applies.
- Consider also adding a context-variable note to the SKILL.md "Context
  Requirements" table: `step8_review_required` (boolean, always true,
  cannot be overridden by profile keys other than a future
  `commit_review: skip`).
- Mirror or cross-reference the same rule in
  `.claude/skills/aitask-pick/SKILL.md` if needed (likely not — picks
  delegate to task-workflow).

## Cross-agent parity follow-up

Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS", after this Claude
Code change lands, suggest follow-up tasks to mirror the change in:
- `.opencode/skills/task-workflow/SKILL.md`
- `.gemini/skills/task-workflow/SKILL.md`
- `.agents/skills/task-workflow/SKILL.md`

## Verification

- `git diff .claude/skills/task-workflow/SKILL.md` shows a prominent
  non-skippable callout at the top of Step 8.
- Manual: re-read Step 8 with the lens of an agent in auto mode — does
  the callout make it impossible to misread the AskUserQuestion as a
  "routine decision"?
- The t645 origin example is preserved in the callout text.
