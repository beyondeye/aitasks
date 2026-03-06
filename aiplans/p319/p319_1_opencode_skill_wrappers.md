---
Task: t319_1_opencode_skill_wrappers.md
Parent Task: aitasks/t319_opencode_support.md
Sibling Tasks: aitasks/t319/t319_2_opencode_setup_install.md, aitasks/t319/t319_3_opencode_docs_update.md, aitasks/t319/t319_4_opencode_model_discovery.md
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Create OpenCode Skill Wrappers and Tool Mapping

## Overview

Create 17 OpenCode skill wrappers in `.opencode/skills/`, a shared tool mapping file, a seed instruction file, and a seed permission config file.

## Step 1: Create the tool mapping file

Create `.opencode/skills/opencode_tool_mapping.md` based on `.agents/skills/codex_tool_mapping.md` but adapted for OpenCode's nearly 1:1 tool compatibility.

**Key differences from Codex mapping:**
- Most tools are direct equivalents (no `exec_command` wrappers needed)
- `AskUserQuestion` → `ask` with `follow_up` array (not `request_user_input`)
- `ask` works in all modes (no plan mode requirement)
- `Agent(...)` → `task` (direct equivalent with `subagent_type`)
- `Skill(name)` → `skill` (native skill loading)
- `EnterPlanMode`/`ExitPlanMode` → plan inline (same as Codex)
- Agent string: `opencode/<model_name>` (reads `aitasks/metadata/models_opencode.json`)

**Reference:** `aidocs/opencode_tools.md` for exact parameter names and formats.

## Step 2: Create 17 skill wrappers

Each wrapper goes in `.opencode/skills/<name>/SKILL.md`. Template is simpler than Codex since no interactive prereqs are needed:

**Simple wrapper template (non-interactive skills):**
```markdown
---
name: aitask-<name>
description: <description from Claude skill>
---

## Source of Truth

This is an OpenCode wrapper. The authoritative skill definition is:

**`.claude/skills/aitask-<name>/SKILL.md`**

Read that file and follow its complete workflow. For tool mapping and
OpenCode adaptations, read **`.opencode/skills/opencode_tool_mapping.md`**.

## Arguments

<skill-specific arguments>
```

**Interactive wrapper template (skills that use AskUserQuestion):**
Same as simple — no prereqs section needed because OpenCode's `ask` works in all modes.

**Skills to create (17 total):**

| # | Skill | Has Interactive? | Arguments |
|---|-------|-------------------|-----------|
| 1 | aitask-changelog | Yes | Optional: `--since <tag>`, `--format <fmt>` |
| 2 | aitask-create | Yes | No args (interactive creation) |
| 3 | aitask-explain | Yes | File path(s) to explain |
| 4 | aitask-explore | Yes | No args |
| 5 | aitask-fold | Yes | Optional task numbers to fold |
| 6 | aitask-pick | Yes | Optional task ID: `319` or `319_2` |
| 7 | aitask-pickrem | No | Optional task ID |
| 8 | aitask-pickweb | No | Optional task ID |
| 9 | aitask-pr-import | Yes | PR URL or number |
| 10 | aitask-refresh-code-models | Yes | No args |
| 11 | aitask-review | Yes | No args |
| 12 | aitask-reviewguide-classify | Yes | Review guide file path |
| 13 | aitask-reviewguide-import | Yes | Source (file, URL, or repo dir) |
| 14 | aitask-reviewguide-merge | Yes | Two review guide file paths |
| 15 | aitask-stats | No | `--days N`, `--verbose`, `--csv [FILE]` |
| 16 | aitask-web-merge | Yes | No args |
| 17 | aitask-wrap | Yes | No args |

**Reference for each wrapper:** Read the corresponding `.agents/skills/aitask-<name>/SKILL.md` Codex wrapper for the exact `name`, `description`, and `Arguments` section. Adapt by:
- Changing "Codex CLI wrapper" → "OpenCode wrapper"
- Changing `.agents/skills/codex_tool_mapping.md` → `.opencode/skills/opencode_tool_mapping.md`
- Removing any "Prerequisites" section that references `codex_interactive_prereqs.md`

## Step 3: Create seed instruction file

Create `seed/opencode_instructions.seed.md` based on `seed/codex_instructions.seed.md`:

```markdown
# aitasks Framework — OpenCode Instructions

For shared aitasks conventions (task file format, task hierarchy,
git operations, commit message format), see `seed/aitasks_agent_instructions.seed.md`.
During `ait setup`, those conventions are installed directly into this file.

The sections below are OpenCode-specific additions.

## Skills

aitasks skills are available in `.opencode/skills/`. Each skill is a wrapper
that references the authoritative Claude Code skill in `.claude/skills/`.
Read the wrapper for tool mapping guidance.

Invoke skills with `/skill-name` syntax (e.g., `/aitask-pick 16`).

## Agent Identification

When recording `implemented_with` in task metadata, identify as
`opencode/<model_name>`. Read `aitasks/metadata/models_opencode.json` to find the
matching `name` for your model ID. Construct as `opencode/<name>`.
```

## Step 4: Create seed permission config

Create `seed/opencode_config.seed.json` with permission whitelist matching `seed/claude_settings.local.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permission": {
    "bash": {
      "*": "ask",
      "git add *": "allow",
      "git commit *": "allow",
      "git push *": "allow",
      "git checkout *": "allow",
      "git merge *": "allow",
      "git worktree *": "allow",
      "git branch *": "allow",
      "git status *": "allow",
      "git diff *": "allow",
      "git log *": "allow",
      "./ait git *": "allow",
      "./aiscripts/aitask_archive.sh *": "allow",
      "./aiscripts/aitask_changelog.sh *": "allow",
      "./aiscripts/aitask_claim_id.sh *": "allow",
      "./aiscripts/aitask_create.sh *": "allow",
      "./aiscripts/aitask_explain_extract_raw_data.sh *": "allow",
      "./aiscripts/aitask_explain_runs.sh *": "allow",
      "./aiscripts/aitask_explain_cleanup.sh *": "allow",
      "./aiscripts/aitask_find_files.sh *": "allow",
      "./aiscripts/aitask_init_data.sh *": "allow",
      "./aiscripts/aitask_issue_import.sh *": "allow",
      "./aiscripts/aitask_issue_update.sh *": "allow",
      "./aiscripts/aitask_lock.sh *": "allow",
      "./aiscripts/aitask_lock_diag.sh *": "allow",
      "./aiscripts/aitask_ls.sh *": "allow",
      "./aiscripts/aitask_pick_own.sh *": "allow",
      "./aiscripts/aitask_pr_close.sh *": "allow",
      "./aiscripts/aitask_pr_import.sh *": "allow",
      "./aiscripts/aitask_query_files.sh *": "allow",
      "./aiscripts/aitask_review_commits.sh *": "allow",
      "./aiscripts/aitask_review_detect_env.sh *": "allow",
      "./aiscripts/aitask_reviewguide_scan.sh *": "allow",
      "./aiscripts/aitask_scan_profiles.sh *": "allow",
      "./aiscripts/aitask_stats.sh *": "allow",
      "./aiscripts/aitask_sync.sh *": "allow",
      "./aiscripts/aitask_update.sh *": "allow",
      "./aiscripts/aitask_web_merge.sh *": "allow",
      "./aiscripts/aitask_zip_old.sh *": "allow",
      "source aiscripts/lib/repo_fetch.sh *": "allow",
      "ls *": "allow",
      "cat *": "allow",
      "echo *": "allow",
      "grep *": "allow",
      "sed *": "allow",
      "sort *": "allow",
      "head *": "allow",
      "tail *": "allow",
      "mkdir *": "allow",
      "cp *": "allow",
      "chmod *": "allow",
      "basename *": "allow",
      "date *": "allow"
    }
  }
}
```

## Step 5: Create project-level OpenCode files

Create `.opencode/instructions.md` for the aitasks repo itself (assembled from Layer 1 + Layer 2, like `.codex/instructions.md`).

## Step 6: Commit

```bash
git add .opencode/skills/ .opencode/instructions.md seed/opencode_instructions.seed.md seed/opencode_config.seed.json
git commit -m "feature: Add OpenCode skill wrappers and tool mapping (t319_1)"
```

## Verification

- [ ] 17 `.opencode/skills/aitask-*/SKILL.md` files exist
- [ ] `.opencode/skills/opencode_tool_mapping.md` exists and is accurate
- [ ] `seed/opencode_instructions.seed.md` follows Layer 2 pattern
- [ ] `seed/opencode_config.seed.json` has permission whitelist matching Claude's
- [ ] `.opencode/instructions.md` assembled for aitasks repo
- [ ] No `opencode_interactive_prereqs.md` needed (OpenCode's `ask` works in all modes)

## Final Implementation Notes

- **Actual work done:** Created all 17 OpenCode skill wrappers, tool mapping file, seed instruction file, seed permission config, and project-level instructions file — exactly as planned.
- **Deviations from plan:** Removed the `<!-- Assembled from ... -->` HTML comment from `.opencode/instructions.md` per user feedback — it's unnecessary in the assembled file.
- **Issues encountered:** None — OpenCode's near-1:1 tool mapping made the wrappers significantly simpler than Codex equivalents (no prerequisites section needed).
- **Key decisions:** OpenCode wrappers use `/skill-name` invocation syntax (matching OpenCode's native skill invocation) instead of Codex's `$skill-name`. No `opencode_interactive_prereqs.md` needed since OpenCode's `ask` tool works in all modes.
- **Notes for sibling tasks:**
  - The tool mapping at `.opencode/skills/opencode_tool_mapping.md` is the central reference for all OpenCode adaptations — sibling tasks should reference it.
  - Permission config at `seed/opencode_config.seed.json` mirrors `seed/claude_settings.local.json` — if new scripts are added, both must be updated.
  - The `.opencode/instructions.md` was manually assembled; t319_2 (setup/install) should automate this assembly in `ait setup`.

## Post-Implementation: Step 9

Follow task-workflow Step 9 for archival.
