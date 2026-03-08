---
Task: t339_3_geminicli_commit_coauthor_support.md
Parent Task: aitasks/t339_codex_contributor.md
Sibling Tasks: aitasks/t339/t339_1_*.md, aitasks/t339/t339_2_*.md, aitasks/t339/t339_4_*.md, aitasks/t339/t339_5_*.md, aitasks/t339/t339_6_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t339_3 — Gemini CLI Support

## Overview

Extend the shared t339 coauthor resolver/procedure to Gemini CLI and validate its output.

## Steps

### 1. Validate Gemini mapping

Ensure Gemini CLI agent/model IDs resolve cleanly to display-name and email-local-part output.

### 2. Add Gemini coverage

Extend `tests/test_codeagent.sh` with Gemini CLI cases using current entries from `aitasks/metadata/models_geminicli.json`.

### 3. Refresh shared docs if needed

Update examples or wording if the shared procedure still reads as Codex-only.

## Verification

- Gemini resolver output uses configured domain
- Gemini tests pass
- shared docs reflect Gemini support accurately

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.
