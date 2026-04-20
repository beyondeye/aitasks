---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [framework, skill, task_workflow, verification]
created_at: 2026-04-20 11:34
updated_at: 2026-04-20 11:34
---

## Problem

The `Manual Verification Follow-up (single-task path)` sub-procedure was added in t583_7 to `.claude/skills/task-workflow/planning.md:334-367`. It is supposed to offer the user a chance to queue a standalone manual-verification task, but it is not firing reliably — recent `/aitask-pick` runs (t597_4, t599, t571_6, t571_9, etc.) completed without it ever being asked.

## Root causes (why the current prompt is missed)

1. **SKILL.md silent on the sub-procedure.** `.claude/skills/task-workflow/SKILL.md:212-224` summarizes what happens after the planning.md Checkpoint (Satisfaction Feedback / restart / Step 7) with zero mention of the follow-up prompt. Agents that lean on the SKILL.md summary skip straight to Step 7.
2. **No guard variable.** Per `feedback_guard_variables`, procedures triggered from multiple entry points need an explicit boolean in the Context Requirements table. There is no `manual_verification_followup_asked` flag — the trigger is pure prose in two places (`planning.md:295` and `planning.md:308`), which is easy to gloss over.
3. **Heading placement.** The `### Manual Verification Follow-up` heading sits at the tail of the Step-6 Checkpoint, after the `If "Abort"` branch, visually indistinguishable from an unrelated subsection.

## Scope of the fix

### 1. Move the prompt to post-implementation

Current placement (post-plan / pre-implementation) cannot catch manual-verification gaps that only surface while running the code. Move the prompt to **after** Step 8's "Commit changes" branch, before Step 9 archival begins. Natural slot: a new `Step 8c: Manual Verification Follow-up` (Step 8b is already deprecated per CLAUDE.md).

Keep the same skip conditions: `is_child == true`, current task `issue_type == manual_verification`, or an aggregate-sibling was created during Step 6 child-task flow.

### 2. Source multiple discovery channels for the checklist seed

When the user picks "Yes, create follow-up task", the current procedure only reads the plan's `## Verification` section. That is too narrow. Extend the seeder input to aggregate from:

- **Plan `## Verification` section** (already done) — bullet lines.
- **Task body `## Verification Steps` section** (from the task file itself) — many tasks have this before a plan is written.
- **Final Implementation Notes** (in the consolidated plan) — especially the "Deviations from plan" and "Issues encountered" fields; these often describe behaviors worth verifying by hand.
- **Diff / commit scan** — `git diff --name-only` on the just-made commit(s): flag touched files matching known interactive surfaces (TUI modules under `.aitask-scripts/board/`, `tui_switcher.py`, `brainstorm/`, `codebrowser/`, `monitor/`, `stats-tui/`; any `.textual`/`.css` themes; shell scripts under `.aitask-scripts/` that open `fzf` or `AskUserQuestion`-style prompts). Emit a suggested bullet per flagged file: `TODO: verify <file> end-to-end in tmux`.
- **Explicit surfacing note to the user.** Before the seeder runs, display the discovered candidate bullets and let the user accept/edit. Do not silently ship the merged list — it should be reviewed once.

Add an explicit reminder in the procedure body: "Before writing `<tmp_checklist>`, scan these sources in order: (a) task body `## Verification Steps`, (b) plan `## Verification`, (c) plan `## Final Implementation Notes`, (d) `git diff --name-only` of the commits just made in Step 8. De-duplicate, then present the merged bullet list to the user for review."

### 3. Mechanical reliability fixes

- **Add a guard variable** `manual_verification_followup_asked: false` to `.claude/skills/task-workflow/SKILL.md` Context Requirements table. Check and set it in the new Step 8c.
- **Mention Step 8c explicitly** in SKILL.md Step 6 post-checkpoint summary AND in the Step 8 → Step 9 handoff language.
- **Remove or deprecate** the current post-plan sub-procedure in `planning.md:334-367` so the prompt only fires once (post-implementation). Update the Step 6 Checkpoint references at `planning.md:295` and `planning.md:308` to simply proceed to Step 7.

## Key Files to Modify

- `.claude/skills/task-workflow/SKILL.md` — add Step 8c, add guard variable to Context Requirements, update Step 6 post-checkpoint summary.
- `.claude/skills/task-workflow/planning.md` — remove the obsolete `### Manual Verification Follow-up (single-task path)` section and the two hooks that jumped to it.
- `.aitask-scripts/aitask_create_manual_verification.sh` — may need a `--merge-items` or multi-source option if the checklist aggregation is done shell-side; otherwise the procedure assembles `<tmp_checklist>` before calling the seeder.

## Cross-agent port

After the Claude Code version lands, suggest separate aitasks to mirror the change in `.gemini/`, `.opencode/`, and `.agents/` trees per the "WORKING ON SKILLS / CUSTOM COMMANDS" rule in CLAUDE.md.

## Verification

- `/aitask-pick` a single-task change (non-child, non-manual_verification), make a trivial code edit, commit in Step 8, and confirm the new Step 8c prompt fires.
- Pick a child task: confirm the prompt is skipped.
- Pick a `manual_verification` task: confirm the prompt is skipped (Check 3 short-circuits to Step 9 anyway).
- Answer "Yes" and confirm: (a) the aggregated candidate-bullet list is displayed for review, (b) the seeder is called with the reviewed list, (c) `MANUAL_VERIFICATION_CREATED:<new_id>:<path>` is parsed and shown.
- Answer "No" and confirm the workflow proceeds to Step 9 without creating a follow-up.
