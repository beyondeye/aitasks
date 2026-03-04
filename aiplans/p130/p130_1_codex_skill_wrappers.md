---
Task: t130_1_codex_skill_wrappers.md
Parent Task: aitasks/t130_codecli_support.md
Sibling Tasks: aitasks/t130/t130_2_codex_setup_install.md, aitasks/t130/t130_3_codex_docs_update.md
Worktree: n/a (working on current branch)
Branch: main
Base branch: main
---

# Plan: Create Codex CLI Skill Wrappers (t130_1)

## Overview

Create 17 Codex CLI wrapper SKILL.md files in `.agents/skills/`, a shared tool mapping file, shared aitasks agent instructions seed, Codex-specific seed files, and project-specific `.codex/` config. Also remove the `AGENTS.md` symlink.

## Architecture Decisions

### 1. Layered Instructions Architecture

Agent instructions follow a two-layer design:

- **Layer 1: Shared** — `seed/aitasks_agent_instructions.seed.md` contains aitasks conventions common to ALL agents (Task File Format, Task Hierarchy, Git Operations, Commit Message Format)
- **Layer 2: Agent-specific** — `seed/codex_instructions.seed.md` contains only Codex CLI-specific additions (skill invocation syntax, agent identification). It references Layer 1 but does NOT duplicate its content.

During `ait setup`, the setup script assembles the final instructions file by combining both layers into the agent's instructions file (e.g., `.codex/instructions.md`).

**Rationale:** Single source of truth for shared content. When conventions change, only `aitasks_agent_instructions.seed.md` needs updating — all agents benefit automatically during setup.

### 2. Shared Tool Mapping File

Instead of duplicating the tool mapping table and Codex CLI adaptations in each of the 17 wrapper SKILL.md files, a single shared file `.agents/skills/codex_tool_mapping.md` contains:
- The Claude Code → Codex CLI tool mapping table
- AskUserQuestion limits (3 options vs Claude's 4, Suggest mode only)
- Plan mode adaptation (inline planning)
- Sub-skill reference handling
- Agent string identification format

Each wrapper references this file: "For tool mapping and Codex CLI adaptations, read `.agents/skills/codex_tool_mapping.md`."

### 3. AGENTS.md Removal

The `AGENTS.md` symlink to `CLAUDE.md` was removed. Each agent now gets its own instructions file via the layered architecture. The `CLAUDE.md` title was updated from `# CLAUDE.md/AGENTS.md` to `# CLAUDE.md`. The `AGENTS.md` reference in `aiscripts/aitask_review_detect_env.sh` was kept (still valid for detecting AI agent config in other projects).

### 4. Project-Specific vs Seed Files

- **Seed files** (`seed/`) are templates installed by `ait setup` into user projects
- **Project files** (`.codex/`, `.agents/`) are the installed/assembled result for THIS project
- `.codex/instructions.md` contains the full assembled content (shared + Codex-specific) with a comment noting its source files
- `.codex/config.toml` matches `seed/codex_config.seed.toml` (no aitasks-project-specific additions needed)

## Files Created

### Seed Files
- `seed/aitasks_agent_instructions.seed.md` — Shared aitasks conventions for all agents
- `seed/codex_instructions.seed.md` — Codex-specific additions (layered, references shared file)
- `seed/codex_config.seed.toml` — Codex sandbox + prefix rules config

### Skill Wrappers (17 files)
- `.agents/skills/codex_tool_mapping.md` — Shared tool mapping and adaptations
- `.agents/skills/aitask-changelog/SKILL.md`
- `.agents/skills/aitask-create/SKILL.md`
- `.agents/skills/aitask-explain/SKILL.md`
- `.agents/skills/aitask-explore/SKILL.md`
- `.agents/skills/aitask-fold/SKILL.md`
- `.agents/skills/aitask-pick/SKILL.md`
- `.agents/skills/aitask-pickrem/SKILL.md`
- `.agents/skills/aitask-pickweb/SKILL.md`
- `.agents/skills/aitask-pr-import/SKILL.md`
- `.agents/skills/aitask-refresh-code-models/SKILL.md`
- `.agents/skills/aitask-review/SKILL.md`
- `.agents/skills/aitask-reviewguide-classify/SKILL.md`
- `.agents/skills/aitask-reviewguide-import/SKILL.md`
- `.agents/skills/aitask-reviewguide-merge/SKILL.md`
- `.agents/skills/aitask-stats/SKILL.md`
- `.agents/skills/aitask-web-merge/SKILL.md`
- `.agents/skills/aitask-wrap/SKILL.md`

### Project-Specific Files
- `.codex/config.toml` — Assembled Codex config for aitasks repo
- `.codex/instructions.md` — Assembled instructions for aitasks repo

### Modified Files
- `CLAUDE.md` — Title updated (removed `/AGENTS.md`)
- `AGENTS.md` — Symlink removed

## Wrapper Template (Compact)

```markdown
---
name: <skill-name>
description: <exact description from Claude Code skill's frontmatter>
---

## Source of Truth

This is a Codex CLI wrapper. The authoritative skill definition is:

**`.claude/skills/<skill-name>/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
Codex CLI adaptations, read **`.agents/skills/codex_tool_mapping.md`**.

## Arguments

<skill-specific argument documentation>
```

## Notes for Sibling Tasks

### For t130_2 (Codex Setup Install)

The setup script (`aiscripts/aitask_setup.sh`) needs to:

1. **Assemble instructions from layers:** During `ait setup`, when Codex CLI is detected:
   - Read `seed/aitasks_agent_instructions.seed.md` (shared layer)
   - Read `seed/codex_instructions.seed.md` (Codex layer)
   - Combine into `.codex/instructions.md` in the target project
   - The assembled file should have shared content first, then Codex-specific sections

2. **Refactor `update_claudemd_git_section()`:** The current function (line ~805 in `aitask_setup.sh`) hardcodes the "Git Operations" section as an inline string. Refactor to read from `seed/aitasks_agent_instructions.seed.md` instead (just the Git Operations section, or the entire shared content). This makes CLAUDE.md consistent with the shared seed file.

3. **Install Codex skill wrappers:** Copy `.agents/skills/` directory (including `codex_tool_mapping.md` and all 17 wrapper dirs) to the target project.

4. **Install Codex config:** Copy/merge `seed/codex_config.seed.toml` into `.codex/config.toml` (similar to how `merge_claude_settings` handles `.claude/settings.local.json`).

5. **Handle existing `.codex/instructions.md`:** If the target project already has Codex instructions, merge/append the aitasks content (like how CLAUDE.md gets the Git Operations section appended).

6. **Consider other agents:** The same layered architecture applies to Gemini CLI and OpenCode. Create corresponding layer-2 seed files:
   - `seed/gemini_instructions.seed.md`
   - `seed/opencode_instructions.seed.md`
   Each references Layer 1 (`aitasks_agent_instructions.seed.md`) and adds agent-specific sections.

### For t130_3 (Codex Docs Update)

1. **Document the layered architecture** in the website/docs
2. **Explain the seed file system:** Layer 1 (shared) + Layer 2 (agent-specific)
3. **Document `$skill-name` invocation** for Codex CLI users
4. **Reference the tool mapping file** `.agents/skills/codex_tool_mapping.md`

## Verification

- [x] All 17 `.agents/skills/<name>/SKILL.md` files exist
- [x] Each wrapper's name/description matches Claude Code skill
- [x] Shared tool mapping in `.agents/skills/codex_tool_mapping.md`
- [x] `seed/aitasks_agent_instructions.seed.md` exists with shared content
- [x] `seed/codex_config.seed.toml` is valid TOML
- [x] `seed/codex_instructions.seed.md` does NOT duplicate shared content (layered)
- [x] `.codex/config.toml` and `.codex/instructions.md` exist
- [x] `AGENTS.md` symlink removed
- [x] CLAUDE.md title updated

## Post-Review Changes

### Change Request 1 (2026-03-04 23:00)
- **Requested by user:** Extract Tool Mapping and Codex CLI Adaptations into a shared file referenced by all wrappers instead of duplicating in each
- **Changes made:** Created `.agents/skills/codex_tool_mapping.md` with shared content; rewrote all 17 wrappers to compact format (~17 lines each) referencing the shared file
- **Files affected:** All 17 `.agents/skills/*/SKILL.md` files, new `.agents/skills/codex_tool_mapping.md`

### Change Request 2 (2026-03-04 23:05)
- **Requested by user:** Make `codex_instructions.seed.md` layered — only Codex-specific additions, not duplicated shared content
- **Changes made:** Rewrote `seed/codex_instructions.seed.md` to reference `seed/aitasks_agent_instructions.seed.md` for shared content; kept only Codex-specific sections (Skills, Agent Identification)
- **Files affected:** `seed/codex_instructions.seed.md`

### Change Request 3 (2026-03-04 23:10)
- **Requested by user:** Document architectural decisions in the plan for sibling tasks
- **Changes made:** Added Architecture Decisions section and Notes for Sibling Tasks section to plan
- **Files affected:** `aiplans/p130/p130_1_codex_skill_wrappers.md`

### Change Request 4 (2026-03-04 23:15)
- **Requested by user:** Simplify preamble in agent instructions to: "This project uses the aitasks framework for task management. Tasks are markdown files with YAML frontmatter stored in git."
- **Changes made:** Updated preamble in all 3 instruction files
- **Files affected:** `seed/aitasks_agent_instructions.seed.md`, `seed/codex_instructions.seed.md`, `.codex/instructions.md`

## Final Implementation Notes

- **Actual work done:** Created 17 Codex CLI skill wrappers, shared tool mapping file, layered agent instructions (shared + Codex-specific), Codex config seed, project-specific `.codex/` files. Removed `AGENTS.md` symlink and updated `CLAUDE.md` title.
- **Deviations from plan:** Original plan specified 14 skills with inline tool mapping; expanded to 17 skills (added pickrem, pickweb, web-merge) with shared tool mapping file. Changed from monolithic to layered instructions architecture per user feedback.
- **Issues encountered:** Initial implementation duplicated content across all wrappers and in codex_instructions.seed.md. Resolved by extracting shared content into referenced files.
- **Key decisions:** (1) Layered instructions: Layer 1 shared + Layer 2 agent-specific. (2) Single shared `codex_tool_mapping.md` for all wrappers. (3) `AGENTS.md` symlink removed — each agent gets its own instructions file.
- **Notes for sibling tasks:** t130_2 needs to implement assembly logic in `ait setup` (combine Layer 1 + Layer 2 into each agent's instructions file), copy `.agents/skills/` to target projects, and refactor `update_claudemd_git_section()` to use the shared seed. t130_3 needs to document the layered architecture and `$skill-name` invocation. See "Notes for Sibling Tasks" section above for full details.

## Step 9 Reference

After implementation, follow task-workflow Step 9 for archival and cleanup.
