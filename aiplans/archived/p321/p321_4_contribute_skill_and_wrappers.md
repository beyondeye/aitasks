---
Task: t321_4_contribute_skill_and_wrappers.md
Parent Task: aitasks/t321_removeautoupdatefromdocsorimplement.md
Sibling Tasks: aitasks/t321/t321_1_*.md, aitasks/t321/t321_2_*.md, aitasks/t321/t321_3_*.md, aitasks/t321/t321_5_*.md
Archived Sibling Plans: aiplans/archived/p321/p321_1_*.md, aiplans/archived/p321/p321_2_*.md
Worktree: (current directory)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: t321_4 — Claude Code Skill + Agent Wrappers

## Overview

Create the Claude Code skill definition (source of truth) and all agent wrappers for `/aitask-contribute`.

## Corrections from Plan Verification

| Original plan | Actual pattern (from aitask-pr-import) |
|---|---|
| `.gemini/skills/aitask-contribute/SKILL.md` | Does NOT exist — Gemini CLI has no per-skill directories |
| `.gemini/commands/aitask-contribute.md` | Should be `.toml` format, not `.md` |
| `.agents/skills/` described as "Codex only" | It's a **unified wrapper** for both Codex CLI AND Gemini CLI |

## Files to Create (5 files)

### A. Source of Truth

**1. `.claude/skills/aitask-contribute/SKILL.md`** (~220 lines)

Frontmatter: `name: aitask-contribute`, `description`, `user-invocable: true`

7-step interactive workflow calling `.aitask-scripts/aitask_contribute.sh`:

- **Step 1: Prerequisites** — Verify `gh` CLI, run `--list-areas`, parse `MODE:<clone|downstream>` + `AREA|<name>|<dirs>|<description>` lines
- **Step 2: Area selection** — `AskUserQuestion` multiSelect with areas + "Other (custom path)"
- **Step 3: File discovery** — Run `--list-changes --area <area>` per area, present files via `AskUserQuestion` multiSelect
- **Step 4: Diff + AI analysis** — Run `--dry-run` with placeholder metadata, analyze diffs, identify logical groups
- **Step 5: Contribution grouping** — If multiple groups, ask user to split/keep/customize
- **Step 6: Motivation & scope** — Per group: title (AI-proposed), motivation (free text), scope (`bug_fix|enhancement|new_feature|documentation|other`), merge approach
- **Step 7: Review & create** — Final dry-run preview, confirm, run without `--dry-run` + `--silent`, display issue URLs

Key differences from aitask-pr-import: No execution profiles, no remote sync, no handoff to task-workflow. This skill creates upstream issues, not local tasks.

### B. Skill Wrappers

**2. `.agents/skills/aitask-contribute/SKILL.md`** (~27 lines, unified Codex CLI + Gemini CLI)
- Pattern: `.agents/skills/aitask-pr-import/SKILL.md`
- Conditional prereqs for Codex/Gemini, source of truth reference, tool mapping

**3. `.opencode/skills/aitask-contribute/SKILL.md`** (~23 lines, OpenCode)
- Pattern: `.opencode/skills/aitask-pr-import/SKILL.md`
- Plan mode prereqs, source of truth reference, tool mapping

### C. Custom Command Wrappers

**4. `.gemini/commands/aitask-contribute.toml`** (~13 lines, Gemini CLI)
- Pattern: `.gemini/commands/aitask-pr-import.toml`
- TOML format with `@` includes and `{{args}}`

**5. `.opencode/commands/aitask-contribute.md`** (~14 lines, OpenCode)
- Pattern: `.opencode/commands/aitask-pr-import.md`
- Markdown with `@` includes and `$ARGUMENTS`

Note: Codex CLI has no custom commands directory — it only uses skills (`.agents/skills/`).

## Implementation Order

1. Create `.claude/skills/aitask-contribute/SKILL.md` first (source of truth)
2. Create all 4 wrappers (independent, can be done in parallel)

## Verification

- YAML frontmatter valid in all SKILL.md files
- TOML valid in `.gemini/commands/aitask-contribute.toml`
- All `@` include paths reference existing files
- Script flags in SKILL.md match `aitask_contribute.sh --help` output

## Final Implementation Notes

- **Actual work done:** Created all 5 planned files. The Claude Code SKILL.md is ~160 lines (shorter than the ~220 estimated) because the workflow is more streamlined than aitask-pr-import (no profiles, no sync, no task-workflow handoff). All wrapper files follow their respective aitask-pr-import patterns exactly.
- **Deviations from plan:**
  - The original task file listed 6 files including `.gemini/skills/aitask-contribute/SKILL.md` — this was corrected during plan verification. Gemini CLI has no per-skill directories; it uses the unified `.agents/skills/` wrapper and `.gemini/commands/*.toml` commands.
  - Gemini command uses `.toml` format (not `.md` as originally specified in the task file).
- **Issues encountered:** None — the implementation was straightforward once the pattern corrections were identified.
- **Key decisions:**
  - No execution profiles for this skill (unlike aitask-pick/explore/pr-import) since it creates upstream issues, not local tasks.
  - Scope options limited to 4 in the AskUserQuestion (bug_fix, enhancement, new_feature, documentation) with "Other" available via AskUserQuestion's built-in Other option, mapping to the script's `other` scope value.
  - The unified `.agents/skills/` wrapper pattern (Codex + Gemini in one file) was followed exactly from aitask-pr-import.
- **Notes for sibling tasks:**
  - t321_3 (documentation) should reference the new `/aitask-contribute` command in the docs/overview section.
  - t321_5 (testing) — the contribute script tests were already included in t321_1. This skill creates no shell scripts, only markdown/TOML files, so no additional shellcheck or script testing needed. However, end-to-end testing of the skill workflow could be added.

## Step 9 Reference
Post-implementation: archive task via task-workflow Step 9.
