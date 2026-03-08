---
Task: t339_4_opencode_commit_coauthor_support.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_1_*.md, aitasks/t339/t339_2_*.md, aitasks/t339/t339_3_*.md, aitasks/t339/t339_5_*.md, aitasks/t339/t339_6_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_4 — OpenCode Support

## Overview

Extend the shared t339 coauthor resolver/procedure to OpenCode and validate handling of OpenCode model IDs.

## Steps

### 1. Validate OpenCode model handling

Ensure OpenCode model identifiers from `models_opencode.json` produce stable display names and email local-parts.

### 2. Add OpenCode coverage

Extend `tests/test_codeagent.sh` with OpenCode cases based on current model metadata.

### 3. Document agent-specific caveats only if necessary

Keep the shared procedure generic unless OpenCode needs a real exception.

## Verification

- OpenCode resolver output uses configured domain
- OpenCode tests pass
- any caveat is grounded in actual model-id behavior

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.
