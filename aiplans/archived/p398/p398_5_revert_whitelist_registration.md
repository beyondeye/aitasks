---
Task: t398_5_revert_whitelist_registration.md
Parent Task: aitasks/t398_aitask_revert.md
Sibling Tasks: aitasks/t398/t398_4_website_documentation.md
Archived Sibling Plans: aiplans/archived/p398/p398_1_revert_analyze_script.md, aiplans/archived/p398/p398_2_revert_skill.md, aiplans/archived/p398/p398_3_post_revert_integration.md, aiplans/archived/p398/p398_6_partial_revert_child_mapping.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t398_5 — Revert Whitelist Registration

## Context

The `aitask-revert` feature (t398) introduced `aitask_revert_analyze.sh` and the `aitask-revert` skill for Claude Code. However, the script was never added to any tool whitelists, and the skill was never registered in Gemini CLI. This means the revert skill prompts for permission on every script invocation, and Gemini CLI users have no access to it at all.

## Steps

### Step 1: Add `aitask_revert_analyze.sh` to Claude Code whitelists

**File:** `.claude/settings.local.json`

Add two entries to the `allowedTools` array (the file has two sections — `./.aitask-scripts/` paths and `./aiscripts/` paths):
- `"Bash(./.aitask-scripts/aitask_revert_analyze.sh:*)"` — insert alphabetically near `aitask_review_commits.sh`
- `"Bash(./aiscripts/aitask_revert_analyze.sh:*)"` — insert alphabetically near `aitask_review_commits.sh`

### Step 2: Add to Claude Code seed template

**File:** `seed/claude_settings.local.json`

Add `"Bash(./.aitask-scripts/aitask_revert_analyze.sh:*)"` alphabetically near `aitask_review_commits.sh`.

### Step 3: Add to Gemini CLI whitelist (runtime)

**File:** `.gemini/policies/aitasks-whitelist.toml`

Add `commandPrefix` rule for the script + `activate_skill` rule for `aitask-revert`.

### Step 4: Add to Gemini CLI seed whitelist

**File:** `seed/geminicli_policies/aitasks-whitelist.toml`

Same two additions as Step 3.

### Step 5: Add to OpenCode seed template

**File:** `seed/opencode_config.seed.json`

Add `"./.aitask-scripts/aitask_revert_analyze.sh *": "allow"` to `permission.bash`.

### Step 6: Create Gemini CLI command file

**File:** `.gemini/commands/aitask-revert.toml` (NEW) — wrapper referencing Claude Code skill.

### Step 7: Create OpenCode skill wrapper

**File:** `.opencode/skills/aitask-revert/SKILL.md` (NEW) — wrapper referencing Claude Code skill.

### Step 8: Create Codex CLI skill wrapper

**File:** `.agents/skills/aitask-revert/SKILL.md` (NEW) — unified wrapper for Codex/Gemini CLI.

## Post-Review Changes

### Change Request 1 (2026-03-17 10:05)
- **Requested by user:** Ensure all platform wrappers are complete, including OpenCode command wrapper
- **Changes made:** Added `.opencode/commands/aitask-revert.md` command wrapper (was initially missing)
- **Files affected:** `.opencode/commands/aitask-revert.md`

## Final Implementation Notes
- **Actual work done:** Added `aitask_revert_analyze.sh` to all 5 whitelist/permission files (Claude Code runtime + seed, Gemini CLI runtime + seed, OpenCode seed). Created 4 new wrapper files: Gemini CLI command (`.gemini/commands/aitask-revert.toml`), OpenCode skill (`.opencode/skills/aitask-revert/SKILL.md`), OpenCode command (`.opencode/commands/aitask-revert.md`), and Codex CLI unified skill (`.agents/skills/aitask-revert/SKILL.md`).
- **Deviations from plan:** Added OpenCode command wrapper and Codex CLI skill wrapper — the original task scope only mentioned Gemini CLI skill registration, but all other skills have wrappers for all platforms so this was the correct scope.
- **Issues encountered:** None
- **Key decisions:** Followed existing wrapper patterns exactly (e.g., aitask-explore wrappers) for each platform. Each wrapper simply references the Claude Code source-of-truth skill file with platform-specific tool mapping prerequisites.
- **Notes for sibling tasks:** No runtime OpenCode config file exists (only the seed template `seed/opencode_config.seed.json`), so the whitelist was only added to the seed. The `.claude/settings.local.json` has two whitelist sections: `./.aitask-scripts/` paths and `./aiscripts/` paths — both need entries for new scripts.

## Step 9 Reference
After implementation, follow task-workflow Step 9 for archival.
