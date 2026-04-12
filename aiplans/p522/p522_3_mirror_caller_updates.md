---
Task: t522_3_mirror_caller_updates.md
Parent Task: aitasks/t522_encapsulate_fold_logic_in_scripts.md
Sibling Tasks: aitasks/archived/t522/t522_1_fold_scripts_and_tests.md, aitasks/archived/t522/t522_2_update_claude_code_callers.md
Archived Sibling Plans: aiplans/archived/p522/p522_1_fold_scripts_and_tests.md, aiplans/archived/p522/p522_2_update_claude_code_callers.md
Worktree: (none — profile fast, create_worktree=false)
Branch: main
Base branch: main
---

# Plan: t522_3 Mirror fold-caller updates into alt-agent frontends

## Context

Parent t522 encapsulates fold logic into helper scripts. t522_1 shipped the scripts (`aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh`) and their tests. t522_2 migrated the `.claude/` skill callers (aitask-fold, task-workflow/planning.md, aitask-explore, aitask-pr-import, aitask-contribution-review) to call those scripts directly, and reduced `task-fold-content.md` / `task-fold-marking.md` to thin reference documents.

Per CLAUDE.md's "WORKING ON SKILLS / CUSTOM COMMANDS" section, Claude Code is the source of truth and changes to skills must be mirrored into the other agent frontends: `.agents/` (Codex CLI / unified), `.gemini/`, `.codex/`, and `.opencode/`. This child (t522_3) is the canonical mirror pass that closes out parent t522.

## Investigation results (completed before planning)

Ran the full inventory command from the task description across all four frontend trees and read every hit. Findings:

### 1. `.agents/skills/` — unified Codex CLI / Gemini CLI wrappers

| Skill | File | Content |
|-------|------|---------|
| aitask-fold | `.agents/skills/aitask-fold/SKILL.md` (27 lines) | Thin source-of-truth wrapper. Points at `.claude/skills/aitask-fold/SKILL.md`. No procedural content. |
| aitask-explore | `.agents/skills/aitask-explore/SKILL.md` (26 lines) | Same — thin delegator to `.claude/skills/aitask-explore/SKILL.md`. |
| aitask-pr-import | `.agents/skills/aitask-pr-import/SKILL.md` (27 lines) | Same — thin delegator to `.claude/skills/aitask-pr-import/SKILL.md`. |
| aitask-contribution-review | **does not exist** | No mirror for this skill in `.agents/`. |
| task-workflow/planning.md | **does not exist** | No `.agents/skills/task-workflow/` directory exists. |

### 2. `.opencode/skills/` — OpenCode wrappers

| Skill | File | Content |
|-------|------|---------|
| aitask-fold | `.opencode/skills/aitask-fold/SKILL.md` (23 lines) | Thin OpenCode wrapper. Points at `.claude/skills/aitask-fold/SKILL.md`. No procedural content. |
| aitask-explore | `.opencode/skills/aitask-explore/SKILL.md` (22 lines) | Same — thin delegator. |
| aitask-pr-import | `.opencode/skills/aitask-pr-import/SKILL.md` (23 lines) | Same — thin delegator. |
| aitask-contribution-review | **does not exist** | No mirror for this skill in `.opencode/`. |
| task-workflow/planning.md | **does not exist** | No `.opencode/skills/task-workflow/` directory exists. |

### 3. `.gemini/commands/` — Gemini CLI command wrappers (TOML)

All three relevant wrappers (`aitask-fold.toml`, `aitask-explore.toml`, `aitask-pr-import.toml`) are 13-line thin wrappers. Each uses `@.claude/skills/<skill>/SKILL.md` to directly import the Claude Code authoritative file. Example (`.gemini/commands/aitask-fold.toml`):

```toml
description = "Identify and merge related tasks into a single task, then optionally execute it."
prompt = """
@.gemini/skills/geminicli_tool_mapping.md
@.gemini/skills/geminicli_planmode_prereqs.md
Execute the following Claude Code skill workflow.
Arguments: {{args}}
@.claude/skills/aitask-fold/SKILL.md
"""
```

### 4. `.opencode/commands/` — OpenCode command wrappers (Markdown)

All three relevant wrappers are 13-line thin wrappers that use `@.claude/skills/<skill>/SKILL.md` the same way as Gemini.

### 5. `.codex/` — Codex CLI global config

Contains only `config.toml` and `instructions.md`. No per-skill files. `.codex/prompts/` does not exist. The Codex CLI skill definitions live in `.agents/skills/` (shared with Gemini CLI), which have already been checked in section 1.

### 6. Reduced reference documents

`task-fold-content.md` and `task-fold-marking.md` are NOT mirrored anywhere (confirmed by `find` across `.agents .gemini .codex .opencode`). Their reduction in t522_2 creates zero mirror work, as noted in the task description.

### 7. Verification grep

```bash
grep -rn "Task Fold Content Procedure\|Task Fold Marking Procedure" .agents .gemini .codex .opencode
```
→ **Zero matches.** No stale procedure name-calls anywhere in the mirror frontends.

## Conclusion

**t522_3 is a no-op verification pass.** Every mirror frontend already delegates to `.claude/skills/<skill>/SKILL.md` via either:
- A prose "Source of Truth" pointer (`.agents/skills/*/SKILL.md`, `.opencode/skills/*/SKILL.md`)
- A direct `@.claude/...` file import (`.gemini/commands/*.toml`, `.opencode/commands/*.md`)

This means t522_2's edits to `.claude/skills/aitask-fold/SKILL.md`, `.claude/skills/aitask-explore/SKILL.md`, and `.claude/skills/aitask-pr-import/SKILL.md` are **automatically inherited** by all alt-agent users — no mirror ports are needed.

The skills that t522_2 also updated but that have no mirror at all — `aitask-contribution-review` (no mirror in any frontend) and `task-workflow/planning.md` (no `task-workflow` subdirectory in any mirror frontend) — also create zero mirror work.

## Implementation

Because no files need to be edited, the "implementation" consists solely of documenting the finding and archiving the task. Steps:

1. **Record the finding in this plan file's Final Implementation Notes** (done at commit time per task-workflow Step 8).

2. **Skip the Step 8 code commit** — there are no code file changes to commit. The plan file will be committed via `./ait git` in Step 8's plan-file commit substep, and the archival script in Step 9 will handle the task-file status update commit.

3. **Archive the task** via `./.aitask-scripts/aitask_archive.sh 522_3`. This automatically:
   - Updates `t522_3_mirror_caller_updates.md` metadata (status → Done, updated_at, completed_at)
   - Removes `t522_3` from parent t522's `children_to_implement` list
   - Archives the parent t522 too (it's the last pending child — t522_1 and t522_2 are already archived)
   - Moves the child task to `aitasks/archived/t522/` and the plan to `aiplans/archived/p522/`
   - Releases locks and creates the archival commit

4. **Push via `./ait git push`.**

## Verification

Already performed during investigation:

1. `find .agents/skills .gemini .codex .opencode \( -name 'aitask-fold*' -o -name 'aitask-explore*' -o -name 'aitask-pr-import*' -o -name 'aitask-contribution-review*' -o -name 'task-fold-*' -o -name 'planning.md' \) -type f` — inventory complete (6 command wrappers + 6 thin skill wrappers; all delegators).
2. `grep -rn "Task Fold Content Procedure\|Task Fold Marking Procedure" .agents .gemini .codex .opencode` — zero matches.
3. Read every mirror SKILL.md file and command wrapper — all delegate to the Claude Code source of truth.
4. N/A — No tests to run (no code changes).

## Notes

- Because the skill mirror architecture is "thin delegator to Claude Code source of truth", the CLAUDE.md guidance about needing to separately update mirror copies is already obsolete for skills that follow this pattern. This is a **structural property** of the current mirror layout, not a coincidence for t522_2.
- For future fold-related (or any SKILL.md-touching) tasks, the mirror pass will remain a no-op as long as the mirror architecture continues to use source-of-truth delegation. Any task spun off as "mirror updates for skill X" should first run this same verification before scheduling real work.
- A follow-up doc task could update CLAUDE.md's "WORKING ON SKILLS / CUSTOM COMMANDS" section to note that mirrors are currently thin delegators and that SKILL.md edits in `.claude/` are auto-inherited — but that is out of scope for t522_3 (it would touch CLAUDE.md, not the fold-caller mirror files).

## Discovered gap: aitask-contribution-review has no mirrors

During inventory, discovered that `aitask-contribution-review` is **missing from all four mirror frontends**:
- No `.agents/skills/aitask-contribution-review/SKILL.md`
- No `.opencode/skills/aitask-contribution-review/SKILL.md`
- No `.gemini/commands/aitask-contribution-review.toml`
- No `.opencode/commands/aitask-contribution-review.md`

Root cause: commit ab3c60b5 (t355_6 "feature: Add contribution review skill and helper script") added only `.claude/skills/aitask-contribution-review/SKILL.md` plus the helper script and seed config. Mirror wrappers were never created. This is an oversight, not a deliberate design choice — `aitask-contribution-review` is a user-invocable skill (unlike `task-workflow`, `ait-git`, `user-file-select`, which all correctly set `user-invocable: false`).

**Scope decision:** User confirmed this should be handled as a **separate follow-up task**, not within t522_3. Rationale: t522_3 is narrowly about mirroring t522_2's fold-caller edits; adding new wrappers for a different skill is a distinct concern that deserves its own task for clarity and traceability.

**Follow-up task to create (after t522_3 archival):** A single-purpose task to add the four missing `aitask-contribution-review` wrapper files, matching the existing delegator patterns used by `aitask-fold`, `aitask-explore`, and `aitask-pr-import`.

## Final Implementation Notes

_(To be filled in after Step 8 per task-workflow.)_
