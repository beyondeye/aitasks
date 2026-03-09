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

## Final Implementation Notes
- **Actual work done:** Added `format_gemini_model_label` to parse and format Gemini CLI models, added the `geminicli` mapping to the display name and email resolver in `aitask_codeagent.sh`. Replaced Test 26 with Gemini CLI test coverage in `tests/test_codeagent.sh`.
- **Deviations from plan:** None. The plan was followed directly and no docs updates were needed since they were generic.
- **Issues encountered:** No issues encountered. Tests passed cleanly.
- **Key decisions:** Chose `Gemini CLI` as the agent prefix in the coauthor display name, and implemented `format_gemini_model_label` using bash regex to convert names like `gemini-3.1-pro-preview` into `3.1 Pro Preview`.
- **Notes for sibling tasks:** The mapping logic is straightforward; OpenCode and others can continue to add their own formatting functions using this established pattern.