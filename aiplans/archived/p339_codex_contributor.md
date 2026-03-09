---
Task: t339_codex_contributor.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339 — Agent Commit Coauthor Decomposition

## Overview

Decompose the parent task into focused child tasks for:
- project-scoped coauthor domain configuration
- shared resolver/procedure work plus Codex support
- Gemini CLI support
- OpenCode support
- website/setup documentation
- a final high-risk Claude Code redesign attempt

The parent task itself should stop after creating the child task files and their plans, then return to `Ready` so only the child tasks are implemented.

## Steps

### 1. Create child tasks

Create six child tasks under `aitasks/t339/` with detailed execution context:
- `t339_1` — project config + `ait setup` support for the coauthor email domain
- `t339_2` — shared commit-attribution resolver/procedure and Codex support
- `t339_3` — Gemini CLI support
- `t339_4` — OpenCode support
- `t339_5` — website/setup documentation
- `t339_6` — Claude Code redesign attempt, kept last and documented as risky

### 2. Create child plans

Write a plan file for each child task under `aiplans/p339/` using current-directory metadata.

### 3. Revert parent ownership state

After child creation:
- set parent `t339` back to `Ready`
- clear `assigned_to`
- release the parent lock

### 4. Commit task-data changes

Commit the new plan files and the parent task state transition as task-data changes.

## Verification

- `aitasks/t339/` contains all six child tasks with detailed context
- `aiplans/p339/` contains all six child plans
- parent task lists all child IDs in `children_to_implement`
- parent task is back to `Ready` with no owner/lock

## Step 9 Reference

Post-implementation for each child: archive via task-workflow Step 9.
