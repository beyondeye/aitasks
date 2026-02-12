---
Task: t99_update_scripts_and_skills_docs.md
---

# Plan: t99 — Update Scripts and Skills Documentation

## Context

The README.md documentation is outdated regarding aitask scripts and skills. Several items are completely missing (`ait changelog`, `/aitask-changelog`, `/aitask-create2`, `/aitask-stats`), and existing entries lack detailed per-command documentation. This plan creates 6 child tasks (5 parallel documentation tasks + 1 consolidation task) to update the README comprehensively.

## Approach: Parallel Snippet Files

Each documentation child task (t99_1 through t99_5) writes its output to a separate markdown snippet file in `aitasks/t99/docs/`. The consolidation task (t99_6) merges all snippets into README.md. This enables true parallel execution without file conflicts.

## Updated README Structure

```
# aitasks
(existing intro, philosophy, key features — keep as-is)

## Quick Install                     (keep)
## What Gets Installed               (keep)

## Command Reference                 (EXPAND)
  (summary table — add `ait changelog` row)
  ### Usage Examples                  (keep)
  ### ait create                      (NEW — from t99_1)
  ### ait ls                          (NEW — from t99_1)
  ### ait update                      (NEW — from t99_1)
  ### ait board                       (NEW — from t99_2)
  ### ait stats                       (NEW — from t99_2)
  ### ait clear-old                   (NEW — from t99_2)
  ### ait setup                       (NEW — from t99_2)
  ### ait issue-import                (NEW — from t99_3)
  ### ait issue-update                (NEW — from t99_3)
  ### ait changelog                   (NEW — from t99_3)

## Claude Code Integration           (EXPAND)
  (summary table — add `/aitask-changelog` row)
  ### /aitask-pick [number]           (UPDATE — from t99_4)
  ### /aitask-create                  (UPDATE — from t99_1)
  ### /aitask-create2                 (NEW — from t99_1)
  ### /aitask-stats                   (NEW — from t99_2)
  ### /aitask-cleanold                (UPDATE — from t99_2)
  ### /aitask-changelog               (NEW — from t99_3)
  ### Execution Profiles              (keep)
  ### Claude Code Permissions         (keep)

## Platform Support                   (keep)
## Task File Format                   (keep)
## Known Issues                       (keep)

## Development                        (EXPAND)
  ### Architecture                    (NEW — from t99_5)
  ### Library Scripts                  (NEW — from t99_5)
  ### Modifying scripts               (keep)
  ### Testing changes                 (keep)
  ### Release process                 (keep)

## License                            (keep)
```

## Child Tasks

### t99_1: Core CRUD Commands (create, ls, update) + create skills

**Snippet file:** `aitasks/t99/docs/01_crud_commands.md`

**Scripts to review and document:**
- `aiscripts/aitask_create.sh` — Interactive + batch task creation.
  - **Interactive flow:** Analyze the source code to document the step-by-step interactive flow: parent task selection (fzf from existing tasks or standalone), metadata prompts (priority, effort, issue type, status via fzf), dependency selection (fzf multi-select from open tasks, sibling dep prompt for child tasks), task name entry (with sanitization), iterative description building (add text blocks, insert file references, preview), final review/edit in $EDITOR, optional git commit.
  - **Batch mode:** Full options table (--batch, --name, --desc, --desc-file, --priority, --effort, --type, --status, --labels, --deps, --parent, --no-sibling-dep, --assigned-to, --issue, --commit, --silent), parent/child creation, auto-numbering.
- `aiscripts/aitask_ls.sh` — List/filter tasks (no interactive mode). Document -v, -s, -l, --children, --all-levels, --tree, limit argument, sort order (blocked → priority → effort).
- `aiscripts/aitask_update.sh` — Update task metadata.
  - **Interactive flow:** Analyze source to document: task selection (fzf or argument), field selection loop (fzf menu of editable fields), per-field editing (priority/effort/status via fzf, labels via multi-select, dependencies via multi-select, description via $EDITOR, rename with sanitization), repeat until done.
  - **Batch mode:** All metadata options, label add/remove, child task management (--add-child, --remove-child), rename, board options.

**Skills to review and document:**
- `.claude/skills/aitask-create/SKILL.md` — Verify existing README docs are current.
- `.claude/skills/aitask-create2/SKILL.md` — NEW docs (missing from README). Terminal-native fzf alternative.

**Key source files:**
- `aiscripts/aitask_create.sh` (lines 36-80 for help, lines 16-32 for batch vars, interactive flow throughout)
- `aiscripts/aitask_ls.sh` (lines 6-51 for help)
- `aiscripts/aitask_update.sh` (lines 64-143 for help, interactive flow in main loop)

### t99_2: Utility Commands (board, stats, clear-old, setup) + utility skills

**Snippet file:** `aitasks/t99/docs/02_utility_commands.md`

**Scripts to review and document:**
- `aiscripts/aitask_board.sh` — Kanban TUI launcher. Document venv detection, required Python packages, terminal capability check.
- `aiscripts/aitask_stats.sh` — Completion statistics. Document -d, -w, -v, --csv options, the 7 statistic types, CSV export format.
- `aiscripts/aitask_clear_old.sh` — Archive old files. Document --dry-run, --no-commit, --verbose, archive behavior.
- `aiscripts/aitask_setup.sh` — Dependency installer. Document OS detection, per-platform installs, venv, shim, permissions merge.

**Skills to review and document:**
- `.claude/skills/aitask-stats/SKILL.md` — NEW docs (missing from README).
- `.claude/skills/aitask-cleanold/SKILL.md` — Verify existing README docs are current.

### t99_3: Integration Commands (issue-import, issue-update, changelog) + changelog skill

**Snippet file:** `aitasks/t99/docs/03_integration_commands.md`

**Scripts to review and document:**
- `aiscripts/aitask_issue_import.sh` — Import GitHub issues.
  - **Interactive flow:** Analyze source to document: platform/repo selection, issue listing with fzf (preview pane showing issue body), metadata review and override prompts (priority, effort, type, labels), duplicate detection, description preview, optional comment inclusion, confirm and commit.
  - **Batch mode:** --issue NUM, --range START-END, --all, --skip-duplicates, --no-comments, platform extensibility.
- `aiscripts/aitask_issue_update.sh` — Update linked issues. Document --close, --no-comment, --dry-run, --commits override, auto-detection via (tNN) pattern.
- `aiscripts/aitask_changelog.sh` — Gather changelog data. Document --gather, --check-version, --from-tag, output format. **NOTE: This command is completely missing from README's command table.**

**Skills to review and document:**
- `.claude/skills/aitask-changelog/SKILL.md` — NEW docs (missing from README). Document full workflow.

### t99_4: /aitask-pick Skill

**Snippet file:** `aitasks/t99/docs/04_pick_skill.md`

**Skill to review and update:**
- `.claude/skills/aitask-pick/SKILL.md` (817 lines) — The existing README docs (lines 125-141) are a brief summary. Expand to cover:
  - Full workflow overview (10 steps)
  - Direct task selection (`/aitask-pick 10` and `/aitask-pick 10_2`)
  - Child task handling and sibling context
  - Plan mode integration (create/verify/reuse)
  - User review cycle with post-review changes
  - Issue update integration
  - Abort handling
  - Reference to Execution Profiles section

### t99_5: Development Section (architecture, libraries)

**Snippet file:** `aitasks/t99/docs/05_development.md`

**Content to write:**
- Architecture overview: `ait` dispatcher → `aitask_*.sh` scripts, skills in `.claude/skills/`, libraries in `aiscripts/lib/`
- `lib/task_utils.sh` — Document exported functions: `resolve_task_file()`, `resolve_plan_file()`, `extract_issue_url()`, `extract_final_implementation_notes()`
- `lib/terminal_compat.sh` — Document exported functions: `die()`, `info()`, `success()`, `warn()`, `ait_check_terminal_capable()`, `ait_is_wsl()`, color variables

### t99_6: Consolidate into README.md (depends on t99_1–t99_5)

**Steps:**
1. Read all snippet files from `aitasks/t99/docs/`
2. Read current README.md
3. Add `ait changelog` row to Command Reference summary table
4. Add `/aitask-changelog` row to Claude Code Integration summary table
5. Insert command subsections after "### Usage Examples"
6. Update/add skill subsections in "Claude Code Integration"
7. Add Architecture + Library Scripts subsections before "### Modifying scripts" in Development
8. Fix typo: "developement" → "development" (line 7)
9. Ensure consistent formatting (heading levels, table alignment)
10. Remove snippet files directory (`aitasks/t99/docs/`)
11. Commit all changes

## Task Dependencies

```
t99_1 (CRUD)         ─┐
t99_2 (Utility)       │
t99_3 (Integration)   ├─→ t99_6 (Consolidate) → archive t99
t99_4 (Pick skill)    │
t99_5 (Development)  ─┘
```

Tasks t99_1–t99_5 are independent and can run in parallel. t99_6 depends on all five.

## Snippet Format Template

Each snippet file should follow this structure for commands:

```markdown
### ait <command>

<One-line description.>

**Interactive mode:**
Describe the step-by-step flow of what the user is prompted for and what they can do at each step.
This is NOT a usage manual — it's a capabilities overview so the user understands what the
interactive mode offers. Keep it comprehensive but brief. Example format:

1. **Parent selection** — Choose to create a standalone task or select a parent task for a child
2. **Priority/Effort** — Select priority (high/medium/low) and effort via fzf
3. **Dependencies** — Multi-select from existing tasks; for child tasks, optionally add previous sibling
4. **Task name** — Enter name (auto-sanitized: lowercase, underscores, max 50 chars)
5. **Description** — Iteratively add text blocks and file references until satisfied
6. **Review & confirm** — Preview the task file, optionally edit in $EDITOR

**Batch mode:**
\`\`\`bash
ait <command> --batch <example args>
\`\`\`

| Option | Description |
|--------|-------------|
| `--flag` | What it does |
```

And for skills:

```markdown
### /aitask-<name>

<One-line description.>

**Usage:**
\`\`\`
/aitask-<name> [args]
\`\`\`

**Features:**
- Feature 1
- Feature 2
```

## Interactive Mode Documentation Guidelines

For scripts that have an interactive mode (`ait create`, `ait update`, `ait issue-import`), the documentation MUST:

1. **Analyze the actual source code** — read the interactive flow functions, not just the help text
2. **List the steps** the user goes through, in order, describing what is asked and what choices are available
3. **Be comprehensive but brief** — this is a capabilities overview, not a step-by-step tutorial
4. **Mention fzf features** where relevant (multi-select, preview panes, filtering)
5. **Note conditional steps** — e.g., "For child tasks, also prompts for sibling dependency"

Scripts with interactive modes to document this way:
- `ait create` — Full interactive creation flow (parent selection → metadata → name → description → review)
- `ait update` — Interactive field selection loop (select field → edit value → repeat or save)
- `ait issue-import` — Interactive issue selection and metadata editing

## Verification

After consolidation (t99_6):
- Verify README renders correctly (check heading hierarchy, table formatting)
- Verify all 10 commands are documented in subsections
- Verify all 6 skills are documented
- Verify summary tables include `ait changelog` and `/aitask-changelog`
- Verify "developement" typo is fixed

## Step 9 (Post-Implementation)

After implementation: archive child tasks/plans, update parent task status, commit.
