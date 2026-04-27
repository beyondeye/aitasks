---
Task: t668_task_workflow_step8_review_nonskippable_guard.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: t668 — Step 8 NON-SKIPPABLE callout

## Context

During task t645 (2026-04-26), the user explicitly flagged: "You did not allow
me to review changes, before commit." Auto mode's "minimize interruptions /
prefer assumptions for routine decisions" guidance was misapplied — the Step 8
review is a deliberate user-checkpoint that the SKILL.md describes as a MUST,
not a routine decision. An auto-memory captured the rule, and t664 (claude-memory
review) spawned t668 to encode the rule directly in the SKILL.md text where
agents will encounter it before reaching the AskUserQuestion definition.

The current Step 8 ([SKILL.md:262-264](.claude/skills/task-workflow/SKILL.md))
opens with:

```markdown
### Step 8: User Review and Approval

After implementation is complete, the user MUST be given the opportunity to review and test changes before any commits are made.
```

This single sentence is easy to skim past, especially when an auto-mode agent
parses the file looking for its next AskUserQuestion. The fix is to insert a
prominent callout block above that paragraph so the rule trips agents
immediately and explicitly cites which profile/auto-mode shortcuts do NOT
cover this prompt.

## Change

Single edit to `.claude/skills/task-workflow/SKILL.md`. Insert a callout
block as the FIRST content under the `### Step 8: User Review and Approval`
heading, before the existing "After implementation is complete..." paragraph.

The callout text (extends the task body's suggested implementation with an
explicit re-prompt rule for the iterative review loop):

```markdown
**⚠️ NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this review.**

The AskUserQuestion below is load-bearing infrastructure, not a routine
confirmation. Auto mode's "minimize interruptions / prefer assumptions for
routine decisions" guidance and execution-profile shortcuts
(`skip_task_confirmation`, `post_plan_action`, etc.) target other prompts in
the flow — they do NOT cover this review. The only valid skips are profile
keys explicitly named in this SKILL.md as covering Step 8 review (currently:
none). Skipping this prompt removes the user's last chance to test the change
before it lands in git.

**Explicit acceptance required — every iteration.** When the user picks
"Need more changes", the loop returns to the top of Step 8: after applying
the requested changes, the AskUserQuestion review prompt MUST be re-issued.
Repeat for every iteration. The ONLY green light to commit is the user
explicitly selecting "Commit changes" with no accompanying notes, requests,
or open concerns. Tacit consent — silence, lack of objection, "looks fine
I guess", a comment that mentions any further change — is NOT acceptance;
keep iterating. There is no upper bound on iterations.

This rule was added after t645, where the user flagged: "You did not allow me
to review changes, before commit."
```

## Out of scope (deliberate)

- **No `step8_review_required` context variable.** The task body's third
  implementation suggestion proposes adding a boolean to the Context
  Requirements table. Skipped because CLAUDE.md states: "Guard variables …
  do NOT force a single execution, so they can't be used to 'remind agents
  to fire a prompt.'" The right mechanism is the prominent callout itself
  plus existing control flow — adding a context variable would be cargo-cult.

- **No mirror in `.claude/skills/aitask-pick/SKILL.md`.** The task body itself
  notes this is "likely not" needed — picks delegate to task-workflow, so the
  callout in task-workflow already covers them.

- **No edits to `.opencode/`, `.gemini/`, `.agents/` parity copies in this
  task.** Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS", source-of-truth
  changes land in `.claude/` first; parity follow-ups are surfaced as separate
  tasks. Will surface this in Post-Review Changes / cross-agent parity
  follow-up after the commit.

## Files modified

- `.claude/skills/task-workflow/SKILL.md` — insert callout under Step 8 heading

## Verification

- `git diff .claude/skills/task-workflow/SKILL.md` shows the callout placed
  immediately under the `### Step 8:` heading, before the "After
  implementation is complete..." paragraph.
- Re-read Step 8 mentally as an auto-mode agent: the **NON-SKIPPABLE** marker
  and explicit list of profile keys (`skip_task_confirmation`,
  `post_plan_action`) that do NOT cover this review should be impossible to
  misread.
- The t645 origin example is preserved in the callout text.
- No other files touched.

## Cross-agent parity follow-up (post-implementation)

After the commit lands, suggest creating follow-up aitasks to mirror the
callout into:
- `.opencode/skills/task-workflow/SKILL.md`
- `.gemini/skills/task-workflow/SKILL.md`
- `.agents/skills/task-workflow/SKILL.md`

These are bullet-point recommendations to surface to the user — not part of
this task's deliverable.

## Step 9 reference

Per task-workflow, after Step 8 commits are made the workflow proceeds to
Step 8c (manual-verification follow-up — likely "no" for a docs-only change)
and then Step 9 (post-implementation), which here means:
- No build verification configured (`verify_build` absent in
  `aitasks/metadata/project_config.yaml`)
- Run `./.aitask-scripts/aitask_archive.sh 668`
- Run `./ait git push`
- Step 9b satisfaction feedback

## Final Implementation Notes

- **Actual work done:** Added the planned NON-SKIPPABLE callout block to
  `.claude/skills/task-workflow/SKILL.md` under `### Step 8: User Review
  and Approval`, placed before the existing "After implementation is
  complete…" paragraph. The callout includes both the auto-mode/profile
  override warning AND the explicit-acceptance-every-iteration rule
  (added after the user's plan-mode clarification).
- **Deviations from plan:** During the Step 8 review the user edited the
  file directly to remove the trailing t645 attribution sentence ("This
  rule was added after t645…"). The historical reference is now
  preserved only in this plan's Context section and in the auto-memory
  `feedback_step8_explicit_acceptance_every_iteration.md`. The plan's
  Verification bullet stating "the t645 origin example is preserved in
  the callout text" is therefore stale — the rule itself stands; only
  the in-callout attribution was trimmed.
- **Issues encountered:** None — single-file documentation edit.
- **Key decisions:**
  - Used the verbatim suggested text from the task body for the
    callout's first paragraph; extended with a second paragraph
    encoding the explicit-acceptance-every-iteration rule the user
    surfaced during plan-mode review.
  - Skipped the task body's "context variable" suggestion
    (`step8_review_required: boolean (always true)`) because CLAUDE.md
    forbids using guard variables to "remind agents to fire a prompt."
  - Did not mirror the rule in `aitask-pick/SKILL.md` since picks
    delegate to task-workflow.
- **Memory written:** `feedback_step8_explicit_acceptance_every_iteration.md`
  + `MEMORY.md` index entry, capturing the explicit-acceptance rule for
  future sessions.
- **Cross-agent parity follow-ups (recommended):** Mirror the callout
  into `.opencode/skills/task-workflow/SKILL.md`,
  `.gemini/skills/task-workflow/SKILL.md`, and
  `.agents/skills/task-workflow/SKILL.md`. Surface these as separate
  tasks per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS".
