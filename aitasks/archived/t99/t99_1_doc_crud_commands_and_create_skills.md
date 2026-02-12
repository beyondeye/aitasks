---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Done
labels: [aitasks]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-02-12 10:56
updated_at: 2026-02-12 11:35
completed_at: 2026-02-12 11:35
---

## Context
This is child task 1 of t99 (Update Scripts and Skills Docs). The parent task updates README.md documentation for all aitask scripts and skills. Each child writes a documentation snippet file; a final consolidation task (t99_6) merges them into README.md.

## Goal
Document the core CRUD commands (create, ls, update) and the create-related skills (/aitask-create, /aitask-create2).

## Output
Write documentation to `aitasks/t99/docs/01_crud_commands.md`. This snippet file will contain markdown sections ready to be inserted into README.md by the consolidation task.

## Scripts to Review and Document

### ait create (`aiscripts/aitask_create.sh`)
- Read the full source code
- **Interactive flow:** Document the step-by-step interactive flow by analyzing the source: parent task selection (fzf from existing tasks or standalone), metadata prompts (priority, effort, issue type, status via fzf), dependency selection (fzf multi-select from open tasks, sibling dep prompt for child tasks), task name entry (with sanitization rules), iterative description building (add text blocks, insert file references, preview), final review/edit in $EDITOR, optional git commit
- **Batch mode:** Document the full options table with all flags: --batch, --name, --desc, --desc-file, --priority, --effort, --type, --status, --labels, --deps, --parent, --no-sibling-dep, --assigned-to, --issue, --commit, --silent
- Key features: auto-numbering from active/archived/compressed tasks, parent/child creation, filename sanitization

### ait ls (`aiscripts/aitask_ls.sh`)
- Read the full source code
- No interactive mode — document all flags: -v, -s/--status, -l/--labels, -c/--children, --all-levels, --tree, [NUMBER] limit
- Document sort order: blocked status → priority (high>medium>low) → effort (low>medium>high)
- Document output formats: normal (parents only), all-levels (flat), tree (hierarchical)

### ait update (`aiscripts/aitask_update.sh`)
- Read the full source code
- **Interactive flow:** Document by analyzing source: task selection (fzf or argument), field selection loop (fzf menu of editable fields), per-field editing (priority/effort/status via fzf, labels via multi-select, dependencies via multi-select, description via $EDITOR, rename with sanitization), repeat until done
- **Batch mode:** Document all options: --priority, --effort, --status, --type, --deps, --labels, --add-label, --remove-label, --description, --desc-file, --name, --boardcol, --boardidx, --issue, --assigned-to, --add-child, --remove-child, --children, --commit, --silent
- Key features: auto-updates updated_at, child task Done handling (removes from parent's children_to_implement)

## Skills to Review and Document

### /aitask-create (`.claude/skills/aitask-create/SKILL.md`)
- Read the skill file
- Verify the existing README documentation (lines 143-157) is still accurate
- Write updated docs if needed

### /aitask-create2 (`.claude/skills/aitask-create2/SKILL.md`)
- Read the skill file
- This skill is MISSING from the README — write new documentation
- It's a terminal-native fzf alternative to /aitask-create

## Documentation Format
Follow the snippet format from the plan: `### ait <command>` headings for commands, `### /aitask-<name>` headings for skills. Include interactive flow steps (numbered list), batch mode options table, key features.

## Verification
- Snippet file contains sections for all 3 commands and 2 skills
- Interactive mode flows match actual source code behavior
- All batch options are documented
- Format is consistent and ready for README insertion
