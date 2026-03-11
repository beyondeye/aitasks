---
Task: t369_4_update_other_agent_skills.md
Parent Task: aitasks/t369_aitask_explain_for_aitask_pick.md
Sibling Tasks: aitasks/t369/t369_*_*.md
Archived Sibling Plans: aiplans/archived/p369/p369_*_*.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Update Other Agent Skills (t369_4)

## Overview

Propagate the historical context gathering changes from t369_3 (Claude Code) to the other supported agent formats: OpenCode, Codex CLI, and Gemini CLI. The key finding from reading the existing agent skills is that they use a **wrapper pattern** -- their pick skills simply reference the Claude Code source of truth rather than maintaining separate copies.

**Dependency:** Requires t369_3 to be completed (Claude Code skills updated).

## Current Agent Skill Architecture

### OpenCode (`.opencode/skills/aitask-pick/SKILL.md`)
```
This is an OpenCode wrapper. The authoritative skill definition is:
.claude/skills/aitask-pick/SKILL.md
```
- Uses wrapper pattern: reads Claude Code SKILL.md as source of truth
- Has its own tool mapping: `.opencode/skills/opencode_tool_mapping.md`
- Has its own plan mode prereqs: `.opencode/skills/opencode_planmode_prereqs.md`
- **No separate task-workflow directory** -- relies on Claude Code's

### Codex CLI (`.agents/skills/aitask-pick/SKILL.md`)
```
This is a unified skill wrapper for Codex CLI and Gemini CLI.
The authoritative skill definition is: .claude/skills/aitask-pick/SKILL.md
```
- Shared wrapper for both Codex CLI and Gemini CLI
- Has tool mappings: `.agents/skills/codex_tool_mapping.md`, `.agents/skills/geminicli_tool_mapping.md`
- **No separate task-workflow directory** -- relies on Claude Code's

### Gemini CLI (`.gemini/skills/`)
- Only has generic skill files: `geminicli_planmode_prereqs.md`, `geminicli_tool_mapping.md`
- No aitask-pick skill file -- uses the `.agents/skills/` wrapper
- **No separate task-workflow directory** -- relies on Claude Code's

## Analysis

Since ALL agents use the wrapper pattern pointing to `.claude/skills/aitask-pick/SKILL.md` and `.claude/skills/task-workflow/planning.md` as the source of truth, the changes from t369_3 automatically flow through to all agents. **No modifications to agent-specific files are needed.**

The only potential concern is whether `AskUserQuestion` (used in the new Step 0a-bis) is properly mapped for each agent. This needs verification.

## Detailed Implementation Steps

### Step 1: Verify no agent-specific task-workflow files exist

Check for task-workflow directories in each agent:
```bash
ls -la .opencode/skills/task-workflow/ 2>/dev/null || echo "Not found"
ls -la .agents/skills/task-workflow/ 2>/dev/null || echo "Not found"
ls -la .gemini/skills/task-workflow/ 2>/dev/null || echo "Not found"
```

Expected: None found. If found, they need the same updates as Step 2-3 of t369_3.

### Step 2: Verify AskUserQuestion mapping in tool mapping files

Read each tool mapping file and verify `AskUserQuestion` is mapped:

**OpenCode** -- Read `.opencode/skills/opencode_tool_mapping.md`:
- Look for `AskUserQuestion` mapping
- It should map to OpenCode's equivalent interactive prompt mechanism

**Codex CLI** -- Read `.agents/skills/codex_tool_mapping.md`:
- Look for `AskUserQuestion` mapping
- Codex uses `request_user_input` in plan mode

**Gemini CLI** -- Read `.agents/skills/geminicli_tool_mapping.md`:
- Look for `AskUserQuestion` mapping
- Gemini uses its own prompt mechanism

### Step 3: Verify wrapper skill files are correctly referencing source of truth

Read each wrapper and confirm:
- `.opencode/skills/aitask-pick/SKILL.md` references `.claude/skills/aitask-pick/SKILL.md`
- `.agents/skills/aitask-pick/SKILL.md` references `.claude/skills/aitask-pick/SKILL.md`

### Step 4: If any issues found in Steps 1-3, fix them

Possible fixes:
- If an agent has its own task-workflow files, add the same context gathering instruction
- If `AskUserQuestion` is not mapped, add the mapping
- If wrapper references are incorrect, fix them

### Step 5: Document findings

If no changes are needed (most likely scenario), document this in the commit message. This task still serves an important role as a verification step.

### Step 6: Commit

If changes were needed:
```bash
./ait git add <changed files>
./ait git commit -m "feature: Propagate historical context gathering to other agents (t369_4)"
```

If no changes needed (verification only):
- No commit needed for this task. The task is still valuable as a verification step.

## Verification

1. Trace the flow for OpenCode: load `.opencode/skills/aitask-pick/SKILL.md` -> follows to `.claude/skills/aitask-pick/SKILL.md` -> Step 0a-bis uses `AskUserQuestion` -> mapped in opencode_tool_mapping.md -> Step 6.1 calls shell script (all agents can run bash)
2. Trace the flow for Codex CLI: load `.agents/skills/aitask-pick/SKILL.md` -> follows to Claude Code -> same flow
3. Trace the flow for Gemini CLI: same as Codex (shared wrapper)
4. Verify no orphaned/stale task-workflow files exist in any agent directory

## Step 9: Post-Implementation

Follow `.claude/skills/task-workflow/SKILL.md` Step 9 for cleanup, archival, and merge.
