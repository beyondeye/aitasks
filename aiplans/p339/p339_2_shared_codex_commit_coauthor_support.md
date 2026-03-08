---
Task: t339_2_shared_codex_commit_coauthor_support.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_1_*.md, aitasks/t339/t339_3_*.md, aitasks/t339/t339_4_*.md, aitasks/t339/t339_5_*.md, aitasks/t339/t339_6_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_2 — Shared Resolver and Codex Support

## Overview

Introduce the reusable commit-attribution resolver and shared workflow procedure, then prove it with Codex.

## Steps

### 1. Add resolver output

Extend `.aitask-scripts/aitask_codeagent.sh` or a shared helper to emit:
- resolved agent string
- coauthor display name
- coauthor email
- full `Co-authored-by:` trailer

### 2. Update workflow procedures

Add a code-agent commit attribution procedure in `.claude/skills/task-workflow/procedures.md` and update Step 8 text in `.claude/skills/task-workflow/SKILL.md`.

### 3. Align direct commit skills

Keep `.claude/skills/aitask-pickrem/SKILL.md`, `.claude/skills/aitask-pickweb/SKILL.md`, and `.claude/skills/aitask-wrap/SKILL.md` consistent with the shared procedure.

### 4. Add Codex tests

Extend `tests/test_codeagent.sh` to cover at least one Codex agent string and final trailer composition.

## Verification

- resolver emits correct Codex coauthor data
- shared workflow docs describe contributor + agent trailer composition
- Codex tests pass

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.
