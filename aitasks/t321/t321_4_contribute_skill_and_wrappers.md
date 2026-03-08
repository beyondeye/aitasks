---
priority: medium
effort: medium
depends: [1]
issue_type: feature
status: Implementing
labels: [auto-update]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-08 09:36
updated_at: 2026-03-08 18:24
---

## Context

This is child task 3 of t321 (aitask-contribute skill). It creates the Claude Code skill definition and all agent wrappers (Gemini CLI, Codex CLI, OpenCode) for the `/aitask-contribute` command.

The skill orchestrates the interactive workflow — all user interaction happens here. It calls the batch-only `aitask_contribute.sh` script (t321_1) for upstream diffing and issue creation.

## Key Files to Create

- `.claude/skills/aitask-contribute/SKILL.md` (~200-250 lines) — Claude Code skill (source of truth)
- `.gemini/skills/aitask-contribute/SKILL.md` (wrapper, ~20 lines)
- `.gemini/commands/aitask-contribute.md` (wrapper, ~15 lines)
- `.agents/skills/aitask-contribute/SKILL.md` (wrapper, ~20 lines)
- `.opencode/skills/aitask-contribute/SKILL.md` (wrapper, ~20 lines)
- `.opencode/commands/aitask-contribute.md` (wrapper, ~15 lines)

## Reference Files for Patterns

- `.claude/skills/aitask-pr-import/SKILL.md` — primary pattern for skill workflow structure
- `.gemini/skills/aitask-pr-import/SKILL.md` — Gemini CLI wrapper pattern
- `.gemini/commands/aitask-pr-import.md` — Gemini CLI command pattern
- `.agents/skills/aitask-pr-import/SKILL.md` — Codex CLI wrapper pattern
- `.opencode/skills/aitask-pr-import/SKILL.md` — OpenCode wrapper pattern
- `.opencode/commands/aitask-pr-import.md` — OpenCode command pattern
- `.gemini/skills/geminicli_tool_mapping.md` — Gemini tool mapping reference
- `.agents/skills/codex_tool_mapping.md` — Codex tool mapping reference
- `.opencode/skills/opencode_tool_mapping.md` — OpenCode tool mapping reference

## Implementation Plan

### Claude Code SKILL.md

```yaml
---
name: aitask-contribute
description: Contribute local aitasks framework changes back to the upstream repository by opening structured GitHub issues.
user-invocable: true
---
```

**Workflow (7 steps):**

**Step 1: Prerequisites check**
- Verify `gh` CLI installed and authenticated
- Detect mode (clone vs downstream) by running:
  ```bash
  ./.aitask-scripts/aitask_contribute.sh --list-areas
  ```
- Parse output to get available areas and mode
- Inform user: "Detected mode: clone/fork" or "Detected mode: downstream project"

**Step 2: Area selection**
- Present available areas via `AskUserQuestion` with `multiSelect: true`:
  - Question: "Which areas of the framework did you modify?"
  - Options: each area from `--list-areas` output (scripts, claude-skills, gemini, codex, opencode, website [clone only])
  - Plus "Other (custom path)" option

**Step 3: File discovery**
- For each selected area, run:
  ```bash
  ./.aitask-scripts/aitask_contribute.sh --list-changes --area <area>
  ```
- Present changed files to user via `AskUserQuestion` with `multiSelect: true`
- Let them confirm/deselect files

**Step 4: Upstream diff + AI analysis**
- For the confirmed files, run:
  ```bash
  ./.aitask-scripts/aitask_contribute.sh --dry-run --area <area> --files <files> --title "placeholder" --motivation "placeholder" --scope enhancement --merge-approach "clean merge"
  ```
- Read generated issue body from stdout
- AI analyzes the diffs: understand what changed, why, scope assessment

**Step 5: Contribution grouping**
- If changes span multiple distinct features/fixes, AI suggests grouping files into separate contributions
- Use `AskUserQuestion` to let user confirm/adjust groups
- Each group becomes a separate GitHub issue

**Step 6: Motivation & scope per contribution**
- For each contribution group, use `AskUserQuestion` to gather:
  - Title (proposed by AI based on diff analysis)
  - Motivation text (free text from user)
  - Scope: bug fix, enhancement, new feature, documentation, other
  - Proposed merge approach (AI suggests, user confirms)

**Step 7: Review & confirm → create issue(s)**
- Show final issue body preview per contribution
- Use `AskUserQuestion`: "Create this issue on beyondeye/aitasks?" → Confirm / Edit / Abort
- If confirmed, run script without `--dry-run`:
  ```bash
  ./.aitask-scripts/aitask_contribute.sh --area <area> --files <files> --title "<title>" --motivation "<motivation>" --scope <scope> --merge-approach "<approach>"
  ```
- Display created issue URL(s)
- Inform user: "When this issue is imported via /aitask-issue-import, your Co-authored-by attribution will be preserved in implementation commits."

### Agent Wrappers

All wrappers follow the exact same pattern as `aitask-pr-import` — thin redirects to the Claude Code SKILL.md with platform-specific tool mapping references:

**Gemini CLI skill** (`.gemini/skills/aitask-contribute/SKILL.md`):
- Reference `.gemini/skills/geminicli_planmode_prereqs.md`
- Source of truth: `.claude/skills/aitask-contribute/SKILL.md`
- Tool mapping: `.gemini/skills/geminicli_tool_mapping.md`

**Gemini CLI command** (`.gemini/commands/aitask-contribute.md`):
- Same structure as `.gemini/commands/aitask-pr-import.md`

**Codex CLI** (`.agents/skills/aitask-contribute/SKILL.md`):
- Reference `.agents/skills/codex_interactive_prereqs.md`
- Source of truth: `.claude/skills/aitask-contribute/SKILL.md`
- Tool mapping: `.agents/skills/codex_tool_mapping.md`

**OpenCode skill** (`.opencode/skills/aitask-contribute/SKILL.md`):
- Reference `.opencode/skills/opencode_planmode_prereqs.md`
- Source of truth: `.claude/skills/aitask-contribute/SKILL.md`
- Tool mapping: `.opencode/skills/opencode_tool_mapping.md`

**OpenCode command** (`.opencode/commands/aitask-contribute.md`):
- Same structure as `.opencode/commands/aitask-pr-import.md`

## Verification Steps

- `.claude/skills/aitask-contribute/SKILL.md` has valid YAML frontmatter with `name`, `description`, `user-invocable: true`
- All wrapper files reference correct source of truth and tool mapping paths
- All wrapper files exist for each platform
- Skill workflow steps reference the correct script paths and flags
- `/aitask-contribute` is listed in Claude Code's available skills
