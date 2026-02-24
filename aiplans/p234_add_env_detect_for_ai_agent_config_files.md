---
Task: t234_add_env_detect_for_ai_agent_config_files.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The aitasks review system auto-detects project environments via `aitask_review_detect_env.sh` to rank relevant review guides. A new `aiagents` environment and `skill_authoring_best_practices.md` guide were recently added to the active `aireviewguides/` directory. However:
1. The detection script has zero logic to detect AI agent config files (skills, commands, CLAUDE.md, AGENTS.md, etc.)
2. The seed directory doesn't include the new environment or guide, so new `ait setup` installs won't get them
3. The guide's `similar_to` field incorrectly references `python/python_style_guide.md`

## Plan

### Step 1: Add aiagents detection to `aitask_review_detect_env.sh`

Add detection across 3 of the 4 existing test functions:

**Test 1 — `test_project_root_files` (weight 3):**
- Check for `CLAUDE.md` or `AGENTS.md` at project root

**Test 2 — `test_file_extensions` (weight 1):**
- Special-case check for files named `SKILL.md`, `AGENTS.md`, `CLAUDE.md` (exact basename match)

**Test 4 — `test_directory_patterns` (weight 2):**
- Check for files under `.claude/skills/`, `.claude/commands/`, `.gemini/skills/`, `.gemini/commands/`, `.opencode/skills/`, `.opencode/commands/`, `.codex/prompts/`, `.agents/skills/`

### Step 2: Fix guide frontmatter
- Remove `similar_to: python/python_style_guide.md` from the guide

### Step 3: Add to seed
- Add `aiagents` to `seed/reviewguides/reviewenvironments.txt`
- Copy guide to `seed/reviewguides/aiagents/skill_authoring_best_practices.md`

### Step 4: Vocabulary — no changes needed
All labels, types, environments already exist in vocabularies.

## Verification

1. `shellcheck aiscripts/aitask_review_detect_env.sh`
2. Test detection with aiagents files (expect score >= 4)
3. Test detection with non-aiagents files (no false positives)

## Final Implementation Notes
- **Actual work done:** All 4 steps implemented as planned — detection logic, frontmatter fix, seed distribution, vocabulary assessment
- **Deviations from plan:** None
- **Issues encountered:** None. Shellcheck only reported pre-existing info-level warnings (SC1091, SC2295), none from new code
- **Key decisions:** Used exact basename matching in Test 2 rather than extension-based detection since `.md` is too generic. Detection covers 5 AI agent ecosystems: Claude Code, Gemini CLI, OpenCode, Codex CLI, and generic `.agents/` directory
