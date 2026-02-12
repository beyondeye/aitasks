---
priority: medium
effort: medium
depends: [t99_2]
issue_type: documentation
status: Ready
labels: [aitasks]
created_at: 2026-02-12 10:56
updated_at: 2026-02-12 10:56
---

## Context
This is child task 3 of t99 (Update Scripts and Skills Docs). The parent task updates README.md documentation for all aitask scripts and skills. Each child writes a documentation snippet file; a final consolidation task (t99_6) merges them into README.md.

## Goal
Document the integration commands (issue-import, issue-update, changelog) and the changelog skill (/aitask-changelog).

## Output
Write documentation to `aitasks/t99/docs/03_integration_commands.md`. This snippet file will contain markdown sections ready to be inserted into README.md by the consolidation task.

## Scripts to Review and Document

### ait issue-import (`aiscripts/aitask_issue_import.sh`)
- Read the full source code (this is the largest script)
- **Interactive flow:** Analyze source to document: platform auto-detection (GitHub via gh CLI), repo detection from git remote, issue listing with fzf (multi-select, preview pane showing issue body/labels/comments), per-issue metadata review (auto-detected priority/effort/type from labels, user can override), duplicate detection and warning, description preview with optional comment inclusion, confirm and create task file, optional git commit
- **Batch mode:** Document options: --batch, --issue/-i NUM, --range START-END, --all, --source/-S PLATFORM, --priority/-p, --effort/-e, --type/-t, --status/-s, --labels/-l, --deps, --parent/-P, --no-sibling-dep, --commit, --silent, --skip-duplicates, --no-comments
- Key features: GitHub label to aitask label mapping, auto issue type detection from labels, platform-extensible architecture (dispatcher pattern)

### ait issue-update (`aiscripts/aitask_issue_update.sh`)
- Read the full source code
- No interactive mode — fully CLI-driven
- Document options: --source/-S PLATFORM, --commits RANGE, --close, --comment-only (default), --no-comment (requires --close), --dry-run
- Document: auto-detection of commits via (tNN) pattern in commit messages, plan file resolution and "Final Implementation Notes" extraction, markdown comment format posted to issues
- Key features: commit range formats (hash1,hash2 or hash1..hash2), dry-run preview

### ait changelog (`aiscripts/aitask_changelog.sh`)
- Read the full source code
- **NOTE: This command is completely missing from the README's command table — it must be added**
- No interactive mode — output-oriented
- Document modes: --gather (output structured data for all tasks since last release tag), --check-version VERSION (check if CHANGELOG.md has a section for version)
- Document options: --from-tag TAG (override base tag), output format (BASE_TAG, ISSUE_TYPE, TITLE, PLAN_FILE, COMMITS, NOTES)
- Key features: semver tag detection, task ID extraction from commit messages, plan file resolution

## Skills to Review and Document

### /aitask-changelog (`.claude/skills/aitask-changelog/SKILL.md`)
- Read the skill file
- This skill is MISSING from the README — write new documentation
- Document the full workflow: gather release data → load and summarize plans → draft changelog entry → ask for version number → version validation → overlap detection → review and finalize → write CHANGELOG.md → commit
- Note: the skill orchestrates the `ait changelog` command and adds AI-powered summarization

## Documentation Format
Follow the snippet format from the plan: `### ait <command>` headings for commands, `### /aitask-<name>` headings for skills. Include interactive flow steps for issue-import, options tables for all, key features.

## Verification
- Snippet file contains sections for all 3 commands and 1 skill
- Interactive mode flow for issue-import matches actual source code
- All batch/CLI options are documented
- ait changelog command is fully documented (it's missing from current README)
- Format is consistent and ready for README insertion
