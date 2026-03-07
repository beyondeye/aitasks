---
priority: high
effort: medium
depends: []
issue_type: feature
status: Ready
labels: [geminicli]
created_at: 2026-03-07 23:21
updated_at: 2026-03-07 23:21
---

Create foundational Gemini CLI wrapper files: tool mapping, plan mode prerequisites, and 17 skill wrappers in `.gemini/skills/`.

## Context

The aitasks framework supports multiple code agents. Claude Code skills (`.claude/skills/`) are the source of truth. Other agents get thin wrappers that reference the Claude Code skills with agent-specific tool mapping. This task creates the Gemini CLI wrappers following the same pattern used for OpenCode (`.opencode/skills/`).

Gemini CLI has a good `AskUserQuestion` equivalent (no constraints), native `activate_skill` for skill invocation, and direct equivalents for most file/search tools. No plan mode toggle exists — planning is done inline.

## Key Files to Modify

All files are NEW — no existing files modified.

- `.gemini/skills/geminicli_tool_mapping.md` — Tool mapping (Claude Code → Gemini CLI)
- `.gemini/skills/geminicli_planmode_prereqs.md` — Plan mode handling guide
- `.gemini/skills/aitask-changelog/SKILL.md`
- `.gemini/skills/aitask-create/SKILL.md`
- `.gemini/skills/aitask-explain/SKILL.md`
- `.gemini/skills/aitask-explore/SKILL.md`
- `.gemini/skills/aitask-fold/SKILL.md`
- `.gemini/skills/aitask-pick/SKILL.md`
- `.gemini/skills/aitask-pickrem/SKILL.md`
- `.gemini/skills/aitask-pickweb/SKILL.md`
- `.gemini/skills/aitask-pr-import/SKILL.md`
- `.gemini/skills/aitask-refresh-code-models/SKILL.md`
- `.gemini/skills/aitask-review/SKILL.md`
- `.gemini/skills/aitask-reviewguide-classify/SKILL.md`
- `.gemini/skills/aitask-reviewguide-import/SKILL.md`
- `.gemini/skills/aitask-reviewguide-merge/SKILL.md`
- `.gemini/skills/aitask-stats/SKILL.md`
- `.gemini/skills/aitask-web-merge/SKILL.md`
- `.gemini/skills/aitask-wrap/SKILL.md`

## Reference Files for Patterns

- `.opencode/skills/opencode_tool_mapping.md` — Pattern for tool mapping file
- `.opencode/skills/opencode_planmode_prereqs.md` — Pattern for plan mode prereqs
- `.opencode/skills/aitask-pick/SKILL.md` — Pattern for skill wrappers
- `aidocs/geminicli_tools.md` — Gemini CLI tools reference (tool names + params)

## Implementation Plan

### Step 1: Create tool mapping file

Create `.gemini/skills/geminicli_tool_mapping.md` following the pattern in `.opencode/skills/opencode_tool_mapping.md` but with Gemini CLI tool names:

| Claude Code Tool | Gemini CLI Equivalent | Notes |
|---|---|---|
| `AskUserQuestion` | Gemini CLI equivalent | Full-featured, no constraints |
| `Bash(command)` | `run_shell_command(command)` | Also requires `description` param |
| `Read(file)` | `read_file(file_path)` | Supports `start_line`/`end_line` |
| `Write(file, content)` | `write_file(file_path, content)` | Auto-creates parent dirs |
| `Edit(file, ...)` | `replace(file_path, old_string, new_string)` | Single occurrence by default |
| `Glob(pattern)` | `glob(pattern)` | Direct equivalent |
| `Grep(pattern)` | `grep_search(pattern)` | Direct equivalent, ripgrep-based |
| `WebFetch(url)` | `web_fetch(prompt)` | URL + analysis instructions |
| `WebSearch(query)` | `google_web_search(query)` | |
| `Agent(...)` | `codebase_investigator` or `generalist` | For sub-agent work |
| `EnterPlanMode` | _(not available)_ | Plan inline in conversation |
| `ExitPlanMode` | _(not available)_ | Plan inline in conversation |
| `Skill(name)` | `activate_skill(name)` | Native skill activation |

Include sections for: AskUserQuestion adaptation, plan mode, sub-skill references, agent string (`geminicli/<model_name>`), and task-workflow adaptations.

### Step 2: Create plan mode prerequisites

Create `.gemini/skills/geminicli_planmode_prereqs.md` following `.opencode/skills/opencode_planmode_prereqs.md`. Gemini CLI has no plan mode toggle — document inline planning approach.

### Step 3: Create 17 skill wrappers

For each skill, create `.gemini/skills/aitask-<name>/SKILL.md` following the OpenCode wrapper pattern. Each wrapper has:
- YAML frontmatter with `name` and `description` (copy from Claude Code skill)
- Plan Mode Prerequisites section referencing `geminicli_planmode_prereqs.md`
- Source of Truth section referencing the Claude Code skill
- Arguments section describing accepted arguments

Get the `description` for each skill from the corresponding `.claude/skills/aitask-<name>/SKILL.md` frontmatter.

## Verification Steps

```bash
# Count all created files (expect 19: 2 shared docs + 17 skill dirs)
find .gemini/skills -name "*.md" | wc -l

# Verify each skill references the correct Claude Code source
for d in .gemini/skills/aitask-*/; do
  name=$(basename "$d")
  grep -l ".claude/skills/$name/SKILL.md" "$d/SKILL.md" || echo "MISSING: $name"
done

# Verify tool mapping is referenced
grep -l "geminicli_tool_mapping.md" .gemini/skills/aitask-*/SKILL.md | wc -l
```
