---
priority: low
effort: medium
depends: [t369_3]
issue_type: feature
status: Implementing
labels: [aitask_explain, aitask_pick, opencode, codex, geminicli]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-11 18:34
updated_at: 2026-03-17 09:44
---

Propagate the planning instruction changes (historical context gathering) to OpenCode, Codex CLI, and Gemini CLI skill/command files. The core instruction is identical since all agents can run shell scripts. Adapt wording for each agent's format.

## Context

After t369_3 updates the Claude Code skills (the source of truth), the same changes need to propagate to the other supported agent formats: OpenCode, Codex CLI, and Gemini CLI. These agents use wrapper skills that point to the Claude Code source of truth, but some have their own task-workflow files that need updating.

The critical insight from reading the existing agent skill files is that OpenCode and Codex/Gemini CLI use a "wrapper" pattern -- their pick skills simply say "read the Claude Code skill as the source of truth." This means the planning.md changes from t369_3 automatically flow through. However, if any agent has its own copy of the task-workflow planning instructions (rather than referencing the Claude Code version), those copies need updating too.

## Key Files to Modify

- **`.opencode/skills/aitask-pick/SKILL.md`** — Currently a wrapper that says "Read `.claude/skills/aitask-pick/SKILL.md`". Since t369_3 modifies the Claude Code SKILL.md, the wrapper automatically picks up the Step 0a-bis changes. **However**, verify that the wrapper references the Claude Code planning.md for step 6.1 too. If OpenCode has its own task-workflow skill files, those need updating.
- **`.agents/skills/aitask-pick/SKILL.md`** — Codex/Gemini CLI wrapper. Same consideration as OpenCode.
- **`.opencode/skills/task-workflow/`** — Check if this directory exists. If OpenCode has its own copy of planning.md or profiles.md, update them.
- **`.agents/skills/task-workflow/`** — Check if Codex/Gemini has its own copy of task-workflow files.
- **`.gemini/skills/`** — Check for any Gemini-specific skill files that need updating.

## Reference Files for Patterns

- **`.opencode/skills/aitask-pick/SKILL.md`** — Shows the wrapper pattern: "This is an OpenCode wrapper. The authoritative skill definition is: `.claude/skills/aitask-pick/SKILL.md`"
- **`.agents/skills/aitask-pick/SKILL.md`** — Shows the Codex/Gemini wrapper pattern: "This is a unified skill wrapper for Codex CLI and Gemini CLI. The authoritative skill definition is: `.claude/skills/aitask-pick/SKILL.md`"
- **`.opencode/skills/opencode_planmode_prereqs.md`** — OpenCode plan mode prerequisites
- **`.agents/skills/codex_tool_mapping.md`** — Codex tool mapping
- **`.agents/skills/geminicli_tool_mapping.md`** — Gemini tool mapping

## Implementation Plan

### Step 1: Check for agent-specific task-workflow files

Check if any agent has its own copy of planning.md or profiles.md:
```bash
ls -la .opencode/skills/task-workflow/ 2>/dev/null
ls -la .agents/skills/task-workflow/ 2>/dev/null
ls -la .gemini/skills/task-workflow/ 2>/dev/null
```

If none exist (which is likely since these agents use wrapper patterns), the main work is simply verifying the wrappers are correct.

### Step 2: If agent-specific task-workflow files exist, update them

For any agent that has its own `planning.md`:
- Add the same historical context gathering instruction as in t369_3
- Adapt any tool references (e.g., OpenCode uses different plan mode tools)

For any agent that has its own `profiles.md`:
- Add the `gather_explain_context` key to the schema table

### Step 3: Verify wrapper skill files reference correct paths

Read each wrapper and verify:
- `.opencode/skills/aitask-pick/SKILL.md` references `.claude/skills/aitask-pick/SKILL.md`
- `.agents/skills/aitask-pick/SKILL.md` references `.claude/skills/aitask-pick/SKILL.md`

No changes needed if the wrappers already reference the Claude Code source of truth (which they do based on current reading).

### Step 4: Check tool mapping files for any needed updates

Read the tool mapping files to see if `AskUserQuestion` (used in Step 0a-bis) has a mapping for each agent:
- `.opencode/skills/opencode_tool_mapping.md`
- `.agents/skills/codex_tool_mapping.md`
- `.agents/skills/geminicli_tool_mapping.md`

If `AskUserQuestion` is already mapped (which it should be since other steps use it), no changes needed.

## Verification Steps

1. **Verify wrapper references**: Read all wrapper skill files and confirm they point to the Claude Code source of truth.
2. **Check for orphaned files**: Ensure no agent has stale copies of task-workflow files that would override the Claude Code version.
3. **Verify tool mapping**: Confirm `AskUserQuestion` is mapped for all agents.
4. **End-to-end conceptual check**: Trace the flow for each agent: agent loads pick skill -> reads wrapper -> follows to Claude Code SKILL.md -> Step 0a-bis uses AskUserQuestion -> Step 6.1 calls shell script. Verify each link works.
