---
Task: t53_import_gh_issue_as_task.md
Branch: main
Base branch: main
---

# Implementation Plan: t53 - Import GitHub Issues as Tasks

## Context

TubeTime uses a bash-based task management system (`aitasks/`). Task t53 adds the ability to import GitHub issues as aitask files using the `gh` CLI, plus a new `issue` metadata field across all task management scripts and the board UI.

This is a complex task split into 5 child tasks.

## Child Task Breakdown

| Task | Description | Depends On | Key Files |
|------|-------------|------------|-----------|
| t53_1 | Add `issue` metadata field to bash scripts | none | `aitask_update.sh`, `aitask_create.sh`, `aitask_ls.sh` |
| t53_2 | Add `issue` metadata field to board UI | none | `aitask_board/aitask_board.py` |
| t53_3 | Create `aitask_import.sh` - batch mode | t53_1 | `aitask_import.sh` (new) |
| t53_4 | Create `aitask_import.sh` - interactive mode | t53_3 | `aitask_import.sh` (extends) |
| t53_5 | Auto-close GitHub issue on task completion | t53_1 | `.claude/skills/aitask-pick/SKILL.md` |

**Key insight:** t53_1 and t53_2 have NO mutual dependency (the Python board uses `yaml.safe_load()` which handles arbitrary YAML keys natively, unlike the bash scripts which explicitly enumerate known fields). They can be done in parallel. t53_5 only depends on t53_1 (needs the `issue` field to exist in task files).

## Design Decisions

- **Field name:** `issue` (stores full URL like `https://github.com/owner/repo/issues/123`) - platform-agnostic
- **Issue filter:** Open issues only
- **Task naming:** Auto-generated from issue title, user can edit before creating
- **Label sync:** Auto-sync GitHub labels to aitask labels, user can add/remove before creating
- **Description handling:** Use `--desc-file` with stdin/tempfile to avoid shell argument length limits for long issue bodies
- **Platform awareness:** Import script and issue closing are designed with platform abstraction from the start (`--source github` default), so adding GitLab/Bitbucket later is straightforward. Board UI and field storage are inherently platform-agnostic (just a URL).
- **Platform extension points:** Clearly marked with `# PLATFORM-EXTENSION-POINT` comments in code. Adding a new platform requires implementing functions at each extension point. See details in t53_3 and t53_5 below.

## Child Task Details

### t53_1: Add `issue` metadata field to bash scripts

**Files:** `aitask_update.sh`, `aitask_create.sh`, `aitask_ls.sh`

**aitask_update.sh changes:**
- Add `BATCH_ISSUE`/`BATCH_ISSUE_SET` variables
- Add `CURRENT_ISSUE` to parsing variables
- Add `--issue` CLI argument
- Add `issue)` case to `parse_yaml_frontmatter()`
- Add `issue` parameter to `write_task_file()` (14th positional param)
- Write `issue:` field in output (between `assigned_to` and `created_at`, only if non-empty)
- Update ALL 4 call sites of `write_task_file()` with the new parameter
- Save/restore `CURRENT_ISSUE` in `handle_child_task_completion()`
- Add `has_update` check for `BATCH_ISSUE_SET`
- Update help text and interactive summary

**aitask_create.sh changes:**
- Add `BATCH_ISSUE` variable
- Add `--issue` CLI argument
- Add `issue` parameter to `create_task_file()` and `create_child_task_file()`
- Pass through in batch mode call sites
- Update help text

**aitask_ls.sh changes:**
- Add `issue_text` variable
- Add `issue)` case to parsing
- Reset in `parse_task_metadata()`
- Show in verbose output

### t53_2: Add `issue` metadata field to aitask_board.py

**File:** `aitask_board/aitask_board.py`

- Create `IssueField` widget class (follow `ParentField` pattern at ~line 620): focusable, shows URL, Enter key opens in browser via `webbrowser.open()`
- Add issue display to `TaskDetailScreen.compose()` after `assigned_to`
- Add compact "GH" indicator to `TaskCard.compose()` when issue is present
- No Task class changes needed (yaml.safe_load already handles arbitrary fields)

### t53_3: Create aitask_import.sh - batch mode

**New file:** `aitask_import.sh`

- Script structure following `aitask_create.sh` patterns
- **Platform abstraction layer:** `--source github` (default). Platform-specific logic isolated in clearly marked functions:
  - Each platform-specific function is marked with `# PLATFORM-EXTENSION-POINT` comment
  - GitHub backend functions (implemented): `github_fetch_issue()`, `github_list_issues()`, `github_map_labels()`, `github_detect_type()`, `github_preview_issue()`, `github_check_cli()`
  - Dispatcher functions route to the correct backend based on `--source`: `source_fetch_issue()` calls `github_fetch_issue()` etc.
  - **To add a new platform (e.g., GitLab):**
    1. Implement `gitlab_fetch_issue()`, `gitlab_list_issues()`, `gitlab_map_labels()`, `gitlab_detect_type()`, `gitlab_preview_issue()`, `gitlab_check_cli()`
    2. Add `gitlab` to the `--source` validation and dispatcher `case` statements (marked with `# PLATFORM-EXTENSION-POINT`)
    3. Each dispatcher has a clear comment block explaining what the function must return
- **Dependency checks:** Check for `gh`, `jq`, `fzf` (interactive only) and `die` with helpful error message if missing (same pattern as existing bash scripts)
- CLI args: `--batch`, `--source PLATFORM`, `--issue NUM`, `--range START-END`, `--all`, plus passthrough args for priority/effort/labels/deps/parent/commit/silent
- Core functions: `fetch_issue()`, `map_labels_to_aitask()`, `detect_issue_type()`, `generate_task_name()`, `check_duplicate_import()`
- `import_single_issue()`: fetch, map labels, detect type, call `aitask_create.sh --batch --desc-file - --issue URL`
- Range and all-issues support via loops
- Duplicate detection: grep for existing `issue: <url>` in aitasks/

### t53_4: Create aitask_import.sh - interactive mode

**File:** `aitask_import.sh` (extends t53_3)

- 4 sub-modes via fzf menu: specific number, fetch & choose, range, all
- Fetch & choose: uses `source_list_issues()` formatted for fzf with preview via `source_preview_issue()`
- Issue preview before import confirmation
- Task name editing: show auto-generated, let user modify
- Label editing: show auto-synced labels, let user add/remove/clear
- Priority/effort selection via fzf
- Duplicate detection with skip/import-anyway option

### t53_5: Auto-close issue on task completion (platform-aware)

**File:** `.claude/skills/aitask-pick/SKILL.md`

**Goal:** When a task with an `issue` field is archived during the aitask-pick post-implementation step (Step 9), automatically close the associated issue with a reference to the implementation.

**Changes to Step 9 of SKILL.md:**
- Add a new sub-step between file archival and the final git commit
- Check if the archived task has an `issue` field in its frontmatter
- If present, detect platform from URL hostname (marked with `# PLATFORM-EXTENSION-POINT` in SKILL.md):
  - `github.com` -> use `gh issue close <number> --comment "..."` (implemented)
  - `gitlab.com` -> use `glab issue close <number> --description "..."` (future, add case here)
  - Unknown platform -> warn user, skip auto-close, provide URL for manual closing
- The platform detection logic is in a clearly commented section so future platforms can be added by adding a new `case` branch
- Comment on the closed issue with:
  - Reference to the commit(s) that implemented the fix/feature
  - Reference to the archived plan file path for full implementation details
  - Brief summary from the task's "Final Implementation Notes"
- Handle gracefully: skip if no `issue` field, warn if CLI tool unavailable/fails
- Ask user for confirmation before closing the issue

**Example closing comment:**
```
Resolved via aitask t53_2. Implementation details: aiplans/archived/p53/p53_2_add_issue_field_board.md

Commits: <commit_hash_range>
```

**For child tasks:** Close the issue when the specific child task is archived (not when the parent is archived), since the child task represents the actual work done.

**For parent tasks with no children:** Close when the parent is archived.

## Verification

- Test `issue` field roundtrip: create task with `--issue`, update it, verify field preserved
- Test board: open board, verify issue indicator on card, verify detail view shows URL, verify Enter opens browser
- Test import batch: `./aitask_import.sh --batch --issue 1 --dry-run`
- Test import interactive: `./aitask_import.sh` and exercise all 4 sub-modes
- Test issue closing: create a test task with `issue` field, archive it via aitask-pick, verify `gh issue close` is called with correct comment
- Build: `JAVA_HOME=/opt/android-studio/jbr ./gradlew assembleDebug` (no app changes, but verify no regressions)

## Post-Implementation

See Step 9 of aitask-pick workflow for archival steps.
