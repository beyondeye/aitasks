---
priority: medium
effort: low
depends: []
issue_type: feature
status: Ready
labels: [task_workflow, aitask_pick, claudeskills]
created_at: 2026-04-27 11:41
updated_at: 2026-04-27 11:41
boardidx: 190
---

Add a step to the planning workflow that requires the agent to search for
in-flight sibling/parent tasks on overlapping components/labels before
adding child tasks that may compete with existing fixes.

## Origin

Spawned from t664 (review claude memories). Encodes the rule from the
auto-memory `feedback_check_sibling_tasks_before_planning_overlap.md`,
which captured a user correction during t653 planning where the agent
proposed an `agentcrew` heartbeat fix child without checking that t650
already had three children mid-flight on the same heartbeat issue. User
pushback: "we have started planning how to tackle this issue in task 650,
look at it before suggesting more changes."

## Rule (verbatim from memory)

> When planning a fix for a multi-layer bug, the user expects you to find
> tasks already addressing nearby layers and **defer to them** instead of
> adding overlapping children.
>
> **Why:** Duplicate or competing children fragment the fix, increase merge
> risk, and confuse "which layer fixed it." The user prefers one canonical
> fix path per layer; siblings should be **complementary, not redundant**.
>
> **How to apply:**
> - Before writing a multi-child plan, `ls aitasks/` and search for tasks
>   with overlapping labels (e.g., `agentcrew`, `ait_brainstorm`) — not just
>   by name. Read child task files of any candidate parent, not only its
>   frontmatter.
> - If a sibling/parent already covers a layer, drop that layer from your
>   plan and add `depends: [<that_parent>]` to your task. Reference the
>   deferral explicitly in the Context section so reviewers can verify the
>   boundary.
> - Keep a child only if it adds defense-in-depth value the existing fix
>   demonstrably does not provide; if it's belt-and-suspenders for the same
>   scenario, drop it.
> - This is not about avoiding all overlap — complementary fixes are fine —
>   but about not *competing* for the same layer.

## Where to add

Target file: `.claude/skills/task-workflow/planning.md`

Section: §6.1 Planning, in the **Complexity Assessment** sub-section,
right before the "If creating child tasks:" branch (or as a new sub-step
between complexity assessment and child-task creation).

Suggested placement: a new sub-step labeled **Sibling-task overlap check**
that fires when the user has confirmed creating child tasks. The check:

1. Identify the labels and component areas the planned children will
   touch.
2. Run `aitask_ls.sh -v -l <label>` for each relevant label, plus a `grep`
   over `aitasks/` for component-name matches.
3. For each match, read the candidate parent's child task files (not just
   frontmatter) to check for in-flight overlap.
4. If overlap is found:
   - Drop the redundant child(ren) from this plan, OR
   - Add `depends: [<other_parent>]` to this task and reference the
     deferral in the Context section.
   - Keep a child only if it adds defense-in-depth value the existing fix
     demonstrably does not provide.

## Implementation suggestions

- Express the step as a numbered procedure with a concrete command
  example, similar to other planning.md sub-steps (e.g., "Ad-Hoc Fold
  Procedure" at lines 113-139).
- Include the t650 vs t653 correction as the worked example.
- Cross-reference CLAUDE.md "Planning Conventions" if helpful (the
  "Refactor duplicates before adding to them" rule there is adjacent in
  spirit).

## Cross-agent parity follow-up

Per CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS":
> Skill/custom command changes and development, if not specified
> otherwise, should be done in the Claude Code version first. When such
> changes take place, suggest to the user to create separate aitasks to
> update the corresponding skills/commands in their codex cli / gemini cli
> / opencode versions.

After this Claude Code change lands, suggest follow-up tasks to mirror
the change in:
- `.opencode/skills/task-workflow/planning.md`
- `.gemini/skills/task-workflow/planning.md`
- `.agents/skills/task-workflow/planning.md`

## Verification

- `git diff .claude/skills/task-workflow/planning.md` shows a new
  numbered sub-step in §6.1.
- The new step references the t650 vs t653 example.
- No other files modified.
- Manual: walk through the planning of a hypothetical multi-child
  parent task and confirm the new step would surface adjacent in-flight
  work.
