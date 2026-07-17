---
Task: t1157_5_remote_explore_core.md
Parent Task: aitasks/t1157_chatlink_multi_workflow_remote_explore.md
Sibling Tasks: aitasks/t1157/t1157_1_*.md … t1157_4_*.md, aitasks/t1157/t1157_6_*.md … t1157_9_*.md
Archived Sibling Plans: aiplans/archived/p1157/p1157_*_*.md
Worktree: (none — profile fast, current branch)
Branch: main
Base branch: main
---

# Plan: t1157_5 — Remote explore core

## Changes

1. Add a static Claude-first relay skill and codeagent operation for the
   `explore` workflow. Reuse the sandbox/relay invariants but prohibit source,
   git, and task mutation by the agent.
2. Open an `explore:` thread for each configured-channel message; use the
   message as context and ask for one native intent: problem, area, idea, or
   documentation.
3. Persist evidence-backed exploration checkpoints and render Continue,
   Redirect, Propose task, Pause, and Abort in the thread. Put findings in the
   rendered interaction, not only agent narration.
4. Apply the 45-minute active/15-minute synthesis budget. Emit an unapproved
   proposal, exit the sandbox, and let the gateway render task metadata and
   Approve/Request changes/Resume/Restart/Abort controls.
5. Route explicit approval to one parent task creation only; do not expose a
   Continue to implementation path.

## Verification

- Cover all four intents, redirect/continue/pause/abort, evidence checkpoints,
  budgets, approval/revision/resume/restart, and latest-HEAD revalidation.
- Add dry-run dispatch and opt-in live relay smoke coverage.

## Step 9 reference

Record final skill/dispatch timeout behavior for future Codex/OpenCode ports.
