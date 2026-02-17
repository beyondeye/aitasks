---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Ready
labels: []
created_at: 2026-02-08 08:04
updated_at: 2026-02-08 08:04
boardidx: 20
boardcol: backlog
---

# Update aitask-pick skill to support hand-off of local session to web

## Summary

Add support in the `aitask-pick` skill (`.claude/skills/aitask-pick/SKILL.md`) for handing off a local Claude Code session to a remote web session on claude.ai. This allows the user to start task selection and planning locally, then continue implementation remotely.

## Motivation

When working on tasks, the local Claude Code CLI is ideal for interactive planning (exploring the codebase, asking clarifying questions, creating a plan). However, once the plan is finalized and approved, the actual implementation can be handed off to a remote session on claude.ai, freeing up the local terminal and allowing the user to monitor progress from the web or mobile app.

## What to Change

### Optimal Hand-off Point

The hand-off should be offered **after plan creation and approval** (between Step 5 and Step 6 in the current SKILL.md). At this point:
- The task has been selected and assigned
- The codebase has been explored
- The implementation plan has been created, saved to a file, and approved by the user
- All context needed for implementation is captured in the plan file

This is the ideal moment because the plan file serves as a self-contained specification that the remote session can follow.

### Changes to SKILL.md

Modify the **Checkpoint** at the end of Step 5 (after the plan is saved) to add a hand-off option. Currently the checkpoint offers:
- "Start implementation"
- "Revise plan"
- "Abort task"

Add a new option:
- **"Hand off to web session"** (description: "Send implementation to a remote Claude.ai session. You can monitor and steer from the web or mobile app.")

When selected, display instructions to the user on how to perform the hand-off.

### Hand-off Instructions to Display

When the user selects "Hand off to web session", display the following:

1. **The command to type:** Instruct the user to type a message starting with `&` to create a remote session, e.g.:
   ```
   & Implement the plan in aiplans/<plan_file>. Follow it step by step. The task definition is in aitasks/<task_file>.
   ```

2. **What happens:** A new web session is created on claude.ai with the current conversation context (including all exploration and planning done so far). The implementation runs in the cloud.

3. **How to monitor:** Use `/tasks` in the local CLI to check progress, or open the session on claude.ai or the Claude iOS app. You can also steer the remote session by providing feedback.

4. **How to pull back locally (teleport):** When the remote session completes, use `/teleport` or `claude --teleport` to pull the session (and its changes) back to the local terminal for review and post-implementation steps (Step 7-8).

## Prerequisites and Caveats

Document these in the hand-off instructions shown to the user:

### Prerequisites
- **GitHub access authorization:** The remote session needs access to the repository. Ensure `gh auth status` shows you're authenticated, and the repo is accessible from claude.ai.
- **Clean git state:** Before teleporting back, the local repo should have no uncommitted changes. The hand-off instruction should warn the user about this.
- **Branch pushed to remote:** If working on a separate branch (created in Step 4), it must be pushed to the remote repository before the remote session can access it. The hand-off step should automatically push the branch:
  ```bash
  git push -u origin aitask/<task_name>
  ```
- **Same account:** The user must be authenticated to the same Claude.ai account both locally and on the web.

### Caveats
- The `&` prefix creates a **new** remote session with current conversation context — it does not "move" the local session. The local session remains active.
- The remote session is a **fork** — local and remote sessions diverge after the hand-off.
- When teleporting back, ensure you're in the **correct repository** and on the **correct branch**.
- File changes made remotely will need to be pulled/fetched locally after teleport.

## Reference Documentation

- **Claude Code hand-off feature:** The `&` prefix sends a task to a remote claude.ai session with the current conversation context. See Claude Code docs on "Moving tasks between web and terminal".
- **Teleport feature:** `/teleport` or `claude --teleport` pulls a remote session back to the local terminal. Requires clean git state, same repo, branch pushed to remote, same account.
- **`/tasks` command:** Lists remote sessions and their status. Press `t` to teleport into a session.

## Files to Modify

- `.claude/skills/aitask-pick/SKILL.md` — Add the hand-off option to the Step 5 checkpoint, add a new sub-step with hand-off instructions, and document prerequisites/caveats.

## Acceptance Criteria

- [ ] The Step 5 checkpoint in SKILL.md includes a "Hand off to web session" option
- [ ] When selected, clear instructions are displayed to the user including the `&` command to type
- [ ] Prerequisites (git state, branch push, auth) are checked/warned about before hand-off
- [ ] Instructions for monitoring (`/tasks`) and pulling back (`/teleport`) are included
- [ ] Caveats about session forking and context transfer are documented
