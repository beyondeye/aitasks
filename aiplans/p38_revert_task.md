---
Task: t38_revert_task.md
Worktree: (none - working on current branch)
Branch: (current branch)
Base branch: main
---

# Implementation Plan: aitask-revert

## Context

The aitasks framework can archive completed tasks (moving files from `aitasks/` to `aitasks/archived/` and optionally compressing them into `old.tar.gz`), but has no way to reverse this process. When a completed task needs to be undone (code changes reverted, task/plan files restored), everything must be done manually. This task creates the inverse of the archive workflow — a new `aitask-revert` CLI command and Claude Code skill.

## Deliverables

1. **`aiscripts/aitask_revert.sh`** — Shell script handling mechanical operations (file listing, restoration, commit detection)
2. **`.claude/skills/aitask-revert/SKILL.md`** — Claude Code skill for interactive workflow
3. **Registration in `ait` dispatcher** — Add `revert` command routing
4. **Permission entry** — Add `Bash(./aiscripts/aitask_revert.sh:*)` to `.claude/settings.local.json`

## File 1: `aiscripts/aitask_revert.sh`

### Interface

```
Usage: aitask_revert.sh [OPTIONS] [TASK_ID]

Arguments:
  TASK_ID              Task number to revert (e.g., 42, t42, 16_2, t16_2)

Commands (mutually exclusive):
  --list               List archived tasks (default if no TASK_ID)
  --list-commits       Show commits associated with a task
  --restore-files      Only restore task/plan files (no git revert)
  (no flag + TASK_ID)  Full info: restore files + list commits for skill

Options:
  --since DATE         Filter --list by completed_at >= DATE (YYYY-MM-DD)
  --dry-run            Show what would happen without changes
  --no-commit          Stage changes but don't commit
  -h, --help           Show help

Output format (structured lines for skill parsing):
  TASK:<task_id>:<filename>:<status>:<completed_at>    Listed archived task
  TASK_TAR:<task_id>:<filename>                         Task found in old.tar.gz
  RESTORED_TASK:<dest_path>                             Task file restored to active dir
  RESTORED_PLAN:<dest_path>                             Plan file restored to active dir
  EXTRACTED_TAR:<archive>:<filename>                    File extracted from tar.gz
  COMMIT:<hash>:<message>                               Associated implementation commit
  NO_COMMITS                                            No implementation commits found
  ERROR:<message>                                       Error message
```

### Functions

**`list_archived_tasks()`** — Scans `aitasks/archived/` directory + `old.tar.gz`
- For each `.md` file in `aitasks/archived/`: extract task_id, filename, status, completed_at from frontmatter
- For `old.tar.gz`: list contents with `tar -tzf`, extract task_id and filename from paths
- Apply `--since` date filter on completed_at (for tar.gz files, extract to temp and read frontmatter)
- Output: `TASK:<id>:<filename>:<status>:<completed_at>` or `TASK_TAR:<id>:<filename>`
- Sort by completed_at descending (most recent first)

**`find_task_commits()`** — Finds implementation commits (reuses pattern from `aitask_issue_update.sh`)
- Search: `git log --oneline --all --grep="(t${task_id})"` for implementation commits
- Output: `COMMIT:<hash>:<message>` per commit, or `NO_COMMITS`
- Also detects child task commits if reverting a parent with children

**`restore_task_file()`** — Moves task file from archive back to active directory
- Source priority: `aitasks/archived/` first, then `old.tar.gz`
- For archived dir: `mv aitasks/archived/t<N>_*.md aitasks/`
- For tar.gz: extract file, copy to `aitasks/`, then remove from tar.gz (rebuild without the file)
- For child tasks: restore to `aitasks/t<parent>/` (create dir if needed)
- Update metadata: reset `status` to `Ready`, remove `completed_at`, update `updated_at`
- Output: `RESTORED_TASK:<path>`

**`restore_plan_file()`** — Same pattern for plan files
- Source: `aiplans/archived/` or `aiplans/archived/old.tar.gz`
- Destination: `aiplans/` (parent) or `aiplans/p<parent>/` (child)
- Output: `RESTORED_PLAN:<path>`

**`remove_from_tar_gz()`** — Removes a specific file from a tar.gz archive
- Extract archive to temp dir
- Remove the target file
- Rebuild archive (or delete archive if now empty)
- Pattern from `aitask_zip_old.sh`: extract → modify → recompress → verify

**`restore_metadata()`** — Resets task metadata for re-work
- `sed_inplace 's/^status: Done/status: Ready/'`
- Remove `completed_at:` line
- Update `updated_at:` to current timestamp

### Key Implementation Details

- Source `lib/terminal_compat.sh` and `lib/task_utils.sh` for shared utilities
- Use `resolve_task_file()` and `resolve_plan_file()` to locate files across active/archived/tar.gz
- Use `task_git` for git operations (worktree-aware)
- Follow same arg parsing pattern as `aitask_archive.sh`
- All shell conventions: `#!/usr/bin/env bash`, `set -euo pipefail`, `sed_inplace()`, portable `grep`/`wc`/`mktemp`

### Reference Files
- `aiscripts/aitask_archive.sh` — Exact inverse; mirror structure and output format
- `aiscripts/aitask_zip_old.sh` — tar.gz manipulation pattern (lines 218-291: `archive_files()`)
- `aiscripts/aitask_issue_update.sh:226-254` — Commit detection pattern (`detect_commits()`)
- `aiscripts/lib/task_utils.sh:124-278` — File resolution and tar.gz helpers

---

## File 2: `.claude/skills/aitask-revert/SKILL.md`

### Skill Frontmatter

```yaml
---
name: aitask-revert
description: Revert a completed task by restoring its files and undoing code changes.
---
```

### Workflow Steps

#### Step 1: Target Selection

**If numeric argument provided** (e.g., `/aitask-revert 42`):
- Run `./aiscripts/aitask_revert.sh --list-commits <task_id>` to verify the task exists and show info
- Read the task file (via `resolve_task_file`) and show a brief summary
- Use `AskUserQuestion` to confirm: "Revert task t<N>: <summary>?"
  - "Yes, proceed" / "No, pick a different task" / "Abort"

**If no argument:**
- Use `AskUserQuestion`: "How far back should we search for completed tasks?"
  - Header: "Date range"
  - Options: "Last 7 days" / "Last 30 days" / "Last 90 days" / "All time"
- Run `./aiscripts/aitask_revert.sh --list [--since <date>]`
- Parse TASK and TASK_TAR output lines
- Present candidates via paginated `AskUserQuestion` (3 per page + "Show more", same pattern as aitask-pick)
- After selection, show task summary and confirm

#### Step 2: Commit Identification

- Run `./aiscripts/aitask_revert.sh --list-commits <task_id>`
- Parse COMMIT lines
- If parent task with children: also find child commits
- Display commits grouped:
  ```
  Implementation commits to revert:
  - <hash> <message>
  - <hash> <message>

  Administrative commits (will NOT be reverted — file restoration handles this):
  - <hash> ait: Archive completed t42...
  - <hash> ait: Start work on t42...
  ```
- Use `AskUserQuestion`:
  - "These implementation commits will be reverted. Confirm?"
  - "Yes, revert these commits" / "Select specific commits" / "Skip code revert (restore files only)" / "Abort"
- If "Select specific commits": present checkboxes with multiSelect

#### Step 3: Execute Revert

**3a: Restore task and plan files:**
```bash
./aiscripts/aitask_revert.sh --restore-files <task_id>
```
Parse RESTORED_TASK and RESTORED_PLAN output. Inform user of restored paths.

**3b: Revert code commits** (unless "restore files only" was chosen):
- Sort commits in reverse chronological order (most recent first)
- For each commit:
  ```bash
  git revert --no-edit <hash>
  ```
- If merge conflict occurs:
  - Inform user of the conflict
  - Use `AskUserQuestion`: "Merge conflict during revert. How to proceed?"
    - "Help me resolve" / "Skip this commit" / "Abort remaining reverts"
  - If "Help me resolve": analyze conflict, suggest resolution, apply
  - If "Skip this commit": `git revert --abort` for that commit, continue
  - If "Abort": `git revert --abort`, stop reverting

#### Step 4: Build Verification

- Read `aitasks/metadata/project_config.yaml` for `verify_build`
- If configured, run the build command(s)
- If build fails:
  - Analyze errors
  - If caused by the revert: create a fix plan, ask user confirmation, implement fixes
  - If pre-existing: log and continue
- If no `verify_build`: skip with message "No verify_build configured — skipping build verification."

#### Step 5: Final Commit

- Use `AskUserQuestion`: "Revert complete. Commit the restored task/plan files?"
  - "Yes, commit" / "No, leave uncommitted"
- If "Yes":
  ```bash
  ./ait git add aitasks/ aiplans/
  ./ait git commit -m "ait: Revert t<N>: restore task and plan files"
  ```
- Ask about push

---

## File 3: Changes to `ait` dispatcher

Add to the `case` statement in `/home/ddt/Work/aitasks/ait` (after `lock)` line):

```bash
revert)       shift; exec "$SCRIPTS_DIR/aitask_revert.sh" "$@" ;;
```

Add to `show_usage()`:

```
  revert         Revert a completed task (restore files, undo commits)
```

## File 4: Permission entry in `.claude/settings.local.json`

Add to the `allow` array:

```json
"Bash(./aiscripts/aitask_revert.sh:*)"
```

---

## Verification

1. **Test listing**: `./ait revert --list` — should show archived tasks
2. **Test listing with date filter**: `./ait revert --list --since 2026-01-01`
3. **Test commit detection**: `./ait revert --list-commits <known_task_id>` — should show `(tN)` commits
4. **Test dry-run restore**: `./ait revert --restore-files --dry-run <task_id>`
5. **Test file restoration from archived/**: Pick a recently archived task, restore, verify files appear in `aitasks/` and `aiplans/`
6. **Test file restoration from old.tar.gz**: Pick a task in old.tar.gz, restore, verify extraction and tar.gz update
7. **Full skill test**: `/aitask-revert` — run through the interactive workflow end-to-end
8. **Shellcheck**: `shellcheck aiscripts/aitask_revert.sh`

## Implementation Order

1. Create `aiscripts/aitask_revert.sh` with all functions
2. Register in `ait` dispatcher and `settings.local.json`
3. Test script CLI independently
4. Create `.claude/skills/aitask-revert/SKILL.md`
5. Run shellcheck
6. End-to-end test with a known archived task

## Step 9 (Post-Implementation) Reference

After implementation: commit with `feature: Add aitask-revert command and skill (t38)`, then archive t38 via the standard task-workflow Step 9 process.
