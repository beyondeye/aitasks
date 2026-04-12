---
priority: low
effort: low
depends: [t522_2]
issue_type: chore
status: Ready
labels: [aitask_fold, task_workflow]
created_at: 2026-04-12 09:55
updated_at: 2026-04-12 09:55
---

## Context

This is the third and final child of parent t522 (encapsulate fold logic in scripts). Children t522_1 (scripts + tests) and t522_2 (Claude Code caller migration) have shipped. This child mirrors t522_2's `.claude/` edits into the other agent frontends — `.agents/`, `.gemini/`, `.codex/`, and `.opencode/` — so that Codex CLI, Gemini CLI, and OpenCode users see the same reduced fold workflow.

Per CLAUDE.md: "Skill/custom command changes and development, if not specified otherwise, should be done in the Claude Code version first." t522_2 was the Claude Code version; this child is the canonical follow-up.

## Dependencies

- Blocked by t522_2. Use the committed `.claude/` diff from t522_2 as the reference for each mirror edit.

## Scope

Only SKILL.md and command-wrapper files need updates. The fold bash scripts themselves live in `.aitask-scripts/` and are shared across all frontends — no copies go into `.gemini/`, `.agents/`, `.codex/`, or `.opencode/`.

Exploration during parent planning (t522) confirmed:
- `.agents/skills/aitask-fold/SKILL.md` exists and mirrors `.claude/skills/aitask-fold/SKILL.md`.
- `.gemini/commands/aitask-fold.toml` and `.opencode/commands/aitask-fold.md` exist as command wrappers with different formats.
- `.codex/` holds only `config.toml` and `instructions.md`; probably no per-skill mirrors.
- **None** of the mirrors contain `task-fold-content.md` or `task-fold-marking.md`, so the reduction of those two files in t522_2 creates no mirror work.

## Key Files to Investigate

Before editing, run an inventory:
```bash
find .agents/skills .gemini .codex .opencode \
  \( -name 'aitask-fold*' -o -name 'aitask-explore*' -o -name 'aitask-pr-import*' -o -name 'aitask-contribution-review*' -o -name 'task-fold-*' -o -name 'planning.md' \) \
  -type f 2>/dev/null
```

For each hit, `diff` it against the corresponding `.claude/` file to see whether t522_2's edits need porting.

## Expected Edits (subject to investigation)

- `.agents/skills/aitask-fold/SKILL.md` — port Step 0b and Step 3 changes from `.claude/skills/aitask-fold/SKILL.md`.
- `.agents/skills/aitask-explore/SKILL.md` — port Step 3 fold substitutions.
- `.agents/skills/aitask-pr-import/SKILL.md` — port Step 5 fold substitutions.
- `.agents/skills/aitask-contribution-review/SKILL.md` — port Step 6 fold substitutions.
- `.agents/skills/task-workflow/planning.md` (if it exists) — port Ad-Hoc Fold Procedure update.
- `.gemini/commands/aitask-fold.toml` and friends — inspect format. If they inline fold-procedure steps, port the script invocations. If they just point at a skill definition file, no edit needed.
- `.opencode/commands/aitask-fold.md` and friends — inspect format. OpenCode uses markdown for commands.
- `.opencode/skills/<name>/SKILL.md` files for fold, explore, pr-import, contribution-review — port from `.claude/` equivalents if present.
- `.codex/prompts/` — unlikely to contain anything, but check.

## Reference Files for Patterns

- **t522_2 committed diff** — the reference. Run `./ait git log --all -- aitasks/t522/t522_2_update_claude_code_callers.md` to find t522_2's completion commits, then inspect the SKILL.md changes.
- **Archived sibling plans** — `aiplans/archived/p522/p522_1_*.md` and `p522_2_*.md` (once t522_2 is archived) capture the exact interface contracts and caller conversion templates.
- **CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" section** — documents which files are mirrors and their format conventions.

## Implementation Plan

### Step 1: Inventory mirrors
Run the `find` command above. Record the list of hits; these are the candidate files to edit.

### Step 2: Diff each candidate against its Claude Code counterpart
For each `.agents/skills/<skill>/SKILL.md` hit, diff against `.claude/skills/<skill>/SKILL.md`. Pay special attention to the sections t522_2 modified (Step 0b / Step 3 / Step 5 / Step 6 depending on the skill).

### Step 3: Port the edits
For each mirror file, apply the same substitutions as t522_2:
- Validation prose → `aitask_fold_validate.sh` invocation with VALID/INVALID parsing.
- Content procedure invocation → `aitask_fold_content.sh` (positional or `--primary-stdin`).
- Marking procedure invocation → `aitask_fold_mark.sh` with `--commit-mode fresh` or `--commit-mode amend`.
- `--commit-mode` choice must match the Claude Code version for that caller.

### Step 4: Handle command-wrapper files
For `.gemini/commands/*.toml` and `.opencode/commands/*.md`:
1. Read the file. If its content is a thin wrapper that invokes the skill (e.g., just a `prompt = "..."` or `description = "..."` line), no edit needed — the wrapper's behavior inherits from the skill file.
2. If its content inlines procedural steps, port the script invocations.

### Step 5: Verify no reduced procedure files were mirrored
Confirm `.agents/`, `.gemini/`, `.codex/`, `.opencode/` do NOT contain `task-fold-content.md` or `task-fold-marking.md`:
```bash
find .agents .gemini .codex .opencode -name 'task-fold-*.md' 2>/dev/null
```
If any unexpected hits appear, decide whether to port the reduction or leave them.

### Step 6: Commit
Commit mirror edits with plain `git`:
```bash
git add .agents/ .gemini/ .opencode/ .codex/
git commit -m "chore: Mirror fold caller updates into .agents/.gemini/.codex/.opencode (t522_3)"
```
Adjust the `git add` list to match only the paths that were actually edited.

## Verification Steps

1. For each edited mirror file, run `diff -u` against its `.claude/` counterpart. The diffs should only reflect frontend-specific formatting (e.g., `.gemini/` TOML syntax vs `.claude/` markdown); the fold script invocations should be identical in structure.
2. `grep -rn "Task Fold Content Procedure\|Task Fold Marking Procedure" .agents .gemini .codex .opencode 2>/dev/null` — after the migration, should produce zero hits (or only in files that are intentionally not updated, with a documented reason).
3. No tests to run — this is a doc/prose task with no code changes.

## Notes

- This child closes out parent t522. After it archives, the parent t522 auto-archives as well (per task-workflow Step 9).
- Because the bash scripts are shared (not duplicated per frontend), the mirror updates are purely doc edits — no script paths to rewrite, no tests to duplicate.
- If t522_2 introduced any `AskUserQuestion` parsing changes that don't translate cleanly to Gemini/Codex/OpenCode idioms, flag those cases and ask the user for guidance rather than guessing at the right mirror syntax.
