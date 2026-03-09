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

### 1. Add `format_opencode_model_label()` to `aitask_codeagent.sh`

Generic formatter that strips provider prefix from cli_id, title-cases hyphen-separated segments, collapses adjacent numeric segments with `.`, and uppercases known acronyms (gpt, glm).

Expected: `opencode/claude-opus-4-6` → `Claude Opus 4.6`, `opencode/gpt-5.1-codex` → `GPT 5.1 Codex`, `opencode/big-pickle` → `Big Pickle`.

### 2. Add `opencode` cases to resolver functions

- `get_agent_coauthor_name()`: `OpenCode/<formatted_label>` (falls back to raw model token)
- `get_agent_coauthor_email()`: `opencode@<domain>`

### 3. Add OpenCode tests to `tests/test_codeagent.sh`

Tests for basic metadata, custom domain, unknown model fallback, GPT-style model. Renumber existing unsupported-agent test.

### 4. Document agent-specific caveats only if necessary

Keep the shared procedure generic unless OpenCode needs a real exception.

## Verification

- `bash tests/test_codeagent.sh` — all tests pass
- OpenCode resolver output uses configured domain
- any caveat is grounded in actual model-id behavior

## Final Implementation Notes

- **Actual work done:** Added `format_opencode_model_label()` to `aitask_codeagent.sh` — a generic formatter that strips provider prefixes from OpenCode cli_ids, title-cases hyphen-separated segments, collapses adjacent numeric segments with dots (e.g., `4-6` → `4.6`), and uppercases known acronyms (GPT, GLM). Added `opencode` cases to `get_agent_coauthor_name()` and `get_agent_coauthor_email()`. Added 4 new tests (tests 22-25) covering basic metadata, custom-domain handling, unknown-model fallback, and GPT-style model formatting. Renumbered existing tests 22-27 → 26-31.
- **Deviations from plan:** None. The implementation followed the plan exactly.
- **Issues encountered:** None. The shared resolver pattern from t339_2 was well-designed for extension.
- **Key decisions:** The `format_opencode_model_label()` uses a generic title-casing approach rather than model-family-specific parsers (unlike Codex/Claude Code which have dedicated formatters for their specific cli_id formats). This is because OpenCode aggregates models from many providers (OpenAI, Claude, Gemini, GLM, Kimi, MiniMax, etc.) with diverse naming conventions. The generic approach handles all of them acceptably. Email local part is `opencode` (matching the agent identifier). Display name format is `OpenCode/<ModelLabel>` (matching the `Agent/ModelLabel` convention).
- **Notes for sibling tasks:** The resolver now supports `codex`, `claudecode`, and `opencode`. Only `geminicli` remains unsupported (test 26 still validates this rejection). The `format_opencode_model_label()` demonstrates a generic approach that could be reused if other agents need similar diverse model handling. No shared procedure caveats were needed — OpenCode fits the generic flow.

## Step 9 Reference

Post-implementation: archive via task-workflow Step 9.
