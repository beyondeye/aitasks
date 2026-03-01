---
Task: t268_9_refresh_code_models_skill.md
Parent Task: aitasks/t268_wrapper_for_claude_code.md
Sibling Tasks: aitasks/t268/t268_3_common_config_library.md through t268_8
Archived Sibling Plans: aiplans/archived/p268/p268_1_core_wrapper_script.md, p268_2_config_infrastructure.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

The codeagent wrapper (t268_1) created `models_*.json` files for 4 agents (Claude, Gemini, Codex, OpenCode) with model entries containing `name`, `cli_id`, `notes`, and `verified` scores. These files exist in both `aitasks/metadata/` and `seed/`. Currently, updating these model lists requires manual web research. This task creates a Claude Code skill that automates this process.

## Implementation Plan

### Step 1: Create skill directory and SKILL.md

**Create:** `.claude/skills/aitask-refresh-code-models/SKILL.md`

Standalone user-invocable skill (like `aitask-changelog`) — no handoff to task-workflow, no bash script backend. Uses Claude's built-in WebSearch/WebFetch tools directly.

**SKILL.md workflow:**

1. Read current `models_*.json` files and `codeagent_config.json`
2. Let user select which agents to refresh (multiSelect AskUserQuestion)
3. Research latest models via WebSearch + WebFetch per agent
4. Compare current vs discovered: NEW / UPDATED / DEPRECATED? / UNCHANGED
5. Present changes to user for approval (apply all / selectively / abort)
6. Update JSON files in `aitasks/metadata/` + conditional `seed/` sync
7. Verify research URLs are still valid (informational)
8. Commit changes via `./ait git` and `git`

### Step 2: Update settings permissions

**Modify:** `.claude/settings.local.json`

Add WebFetch domain permissions for model research URLs:
- `docs.anthropic.com`, `platform.claude.com`, `ai.google.dev`, `platform.openai.com`, `opencode.ai`

`WebSearch` and `WebFetch(domain:developers.openai.com)` already allowed.

## Key Design Decisions

1. **No bash script** — Pure SKILL.md instructions using Claude's WebSearch/WebFetch tools
2. **Sequential agent processing** — One agent at a time for manageable context
3. **Never auto-remove models** — Deprecated flags informational only, removal requires explicit approval
4. **Conditional seed sync** — Check if `seed/` exists before syncing
5. **Research URLs in SKILL.md** — Dedicated section for self-update verification
6. **Agent selection** — User chooses which agents to refresh at the start

## Files to Create/Modify

| Action | File |
|--------|------|
| Create | `.claude/skills/aitask-refresh-code-models/SKILL.md` |
| Modify | `.claude/settings.local.json` (add WebFetch domain permissions) |

## Verification

1. Skill appears in Claude Code's skill list
2. `/aitask-refresh-code-models` triggers the workflow
3. WebSearch and WebFetch work for research URLs
4. Changes presented correctly with IN USE markers
5. JSON files updated in both locations with correct schema
6. `./ait codeagent list-models` shows updated models after refresh

## Final Implementation Notes

- **Actual work done:** Created `.claude/skills/aitask-refresh-code-models/SKILL.md` with complete 8-step workflow (read configs, select agents, web research, compare, present changes, update JSON, verify URLs, commit). Added 4 WebFetch domain permissions to `.claude/settings.local.json`.
- **Deviations from plan:** Updated Anthropic documentation URLs from `docs.anthropic.com` to `platform.claude.com` based on user feedback that the docs have migrated. Removed `docs.anthropic.com` WebFetch permission (no longer needed). Did not add `github.com` WebFetch permission per user request.
- **Issues encountered:** None.
- **Key decisions:**
  - Skill is pure SKILL.md (no bash script) — uses Claude's built-in WebSearch/WebFetch tools
  - User selects which agents to refresh at the start (multiSelect)
  - Never auto-removes models — deprecated flags informational only
  - Seed sync is conditional (checks if `seed/` directory exists)
  - Research URLs in a dedicated SKILL.md section for easy maintenance and self-verification
- **Notes for sibling tasks:**
  - The skill is standalone — no integration with other skills or task-workflow needed
  - If new agents are added to codeagent in the future, their `models_*.json` files will be auto-discovered by the skill (Step 1 uses Glob)
