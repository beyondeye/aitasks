---
Task: t339_6_claudecode_coauthor_redesign.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_1_*.md, aitasks/t339/t339_2_*.md, aitasks/t339/t339_3_*.md, aitasks/t339/t339_4_*.md, aitasks/t339/t339_5_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_6 — Claude Code Redesign Attempt

## Overview

Attempt to replace Claude Code’s native coauthor trailer with the new custom agent+model format, while treating failure as acceptable if native behavior cannot be safely suppressed.

## Steps

### 1. Confirm current Claude behavior

Verify whether Claude’s existing coauthor trailer is tool-native and whether the workflow can influence or suppress it.

### 2. Attempt safe replacement

If safe, route Claude through the same custom resolver used by the other agents.

### 3. Guard against duplication

Do not ship a change that produces both native Claude attribution and the custom trailer on the same commit.

### 4. Fall back cleanly

If replacement is unsafe or impossible, leave Claude unchanged and document the limitation.

## Verification

- duplicate Claude coauthor trailers are explicitly tested
- replacement is only shipped if safe in practice
- fallback documentation is added if Claude must remain special

## Final Implementation Notes

- **Actual work done:** Added `claudecode` support to the shared coauthor resolver in `aitask_codeagent.sh`: a `format_claude_model_label()` function that parses `claude-<family>-<major>-<minor>[-<date>]` CLI IDs into display labels (e.g., `Opus 4.6`), `claudecode` cases in `get_agent_coauthor_name()` and `get_agent_coauthor_email()`, and 4 new tests (tests 18-21) covering basic metadata, custom domain, unknown model fallback, and haiku date suffix stripping. Added an anti-duplication guard note to `procedures.md` stating the resolver trailer replaces any native defaults.
- **Deviations from plan:** The original plan anticipated that Claude Code has a "native tool behavior" that might be impossible to suppress, potentially requiring a documented safe no-op as the outcome. Investigation revealed the Claude trailer (`Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>`) is just system prompt instructions, not automatic tool injection. The workflow's Step 8 already composes full commit messages via heredoc, so the resolver trailer naturally replaces the native one. No suppression mechanism was needed — the task was simpler than feared.
- **Issues encountered:** None. The shared resolver pattern from t339_2 was well-designed for extension, and adding `claudecode` followed the exact same pattern as Codex.
- **Key decisions:** Display name format is `Claude Code/Opus 4.6` (matching the `Agent/ModelLabel` convention used by Codex). Email local part is `claudecode` (matching the agent identifier). The date suffix in haiku's CLI ID (`claude-haiku-4-5-20251001`) is stripped to produce clean `Haiku 4.5` labels.
- **Notes for sibling tasks:** The resolver now supports both `codex` and `claudecode`. Gemini CLI (t339_3) and OpenCode (t339_4) can follow the same pattern: add a `format_<agent>_model_label()` function, add cases to `get_agent_coauthor_name()` and `get_agent_coauthor_email()`, and add corresponding tests. The `geminicli` rejection in test 22 still validates that unsupported agents fail.

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.
