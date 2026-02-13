---
Task: t108_force_git_pull_at_start_of_task_create.md
Worktree: (none - worked on main branch)
Branch: main
Base branch: main
---

# Plan: Duplicate Task ID Prevention (t108)

## Context

When multiple PCs create tasks via `aitask_create.sh` or the `aitask-create` skill, each scans local files for `max(task_id) + 1`. If local repos are out of sync, two PCs assign the same task number. Renaming archived tasks is not an option because commit messages and tools (`ait changelog`, `ait issue-update`) reference task numbers.

**Solution:** Two-part approach:
1. **Draft workflow**: Tasks are created as local drafts in `aitasks/new/` with timestamp-based names. No final task number is assigned yet. Drafts are gitignored (purely local).
2. **Atomic finalization**: When a draft is finalized, the real task number is claimed atomically from a shared counter on a separate git branch (`aitask-ids`). The file is renamed, moved to `aitasks/`, and committed.

This gives us: offline drafting capability, guaranteed unique IDs on finalization, and no risk of archived task renaming.

## Implementation Steps

### Step 1: Create `aiscripts/aitask_claim_id.sh` (new file) - COMPLETED

Standalone script with `--init`, `--claim`, and `--peek` modes. Uses git plumbing (hash-object, mktree, commit-tree) for atomic operations on the `aitask-ids` branch. Retry with random backoff on push rejection (race condition).

### Step 2: No `ait` dispatcher changes - COMPLETED

`aitask_claim_id.sh` is internal - not exposed via `ait` dispatcher.

### Step 3: `.gitignore` update in `ait setup` - COMPLETED

Added `setup_draft_directory()` to `aitask_setup.sh`.

### Step 4: Modify `aiscripts/aitask_create.sh` - COMPLETED

Major rework with draft/finalize workflow: `--finalize`, `--finalize-all` flags, interactive draft management, atomic ID claiming with local-scan fallback.

### Step 5: Update `aitask-create` skill SKILL.md - COMPLETED

Updated to use draft workflow: create in `aitasks/new/`, finalize via `--batch --finalize`.

### Step 6: Update `aitask-pick` skill SKILL.md - COMPLETED

Added Step 0c: `git pull --ff-only --quiet` for best-effort sync before task selection.

### Step 7: Add setup functions to `aitask_setup.sh` - COMPLETED

Added `setup_id_counter()` and `setup_draft_directory()`, called in main().

### Step 8: Add duplicate warnings - COMPLETED

`aitask_ls.sh`: warns on stderr about duplicate task IDs.
`aitask_update.sh`: improved error message for multiple task files.

### Step 9: Automated Tests - COMPLETED

- `tests/test_claim_id.sh`: 10 tests (14 assertions) - ALL PASSED
- `tests/test_draft_finalize.sh`: 13 tests (34 assertions) - ALL PASSED
- `tests/test_setup_git.sh`: 3 new tests (all passed; 4 pre-existing failures unrelated to this change)

## Final Implementation Notes

- **Actual work done:** All 9 steps of the plan were implemented as specified. The atomic counter uses a separate git branch `aitask-ids` with a single `next_id.txt` file. Draft tasks are created in `aitasks/new/` (gitignored) and finalized by claiming an ID from the counter and moving to `aitasks/`.

- **Deviations from plan:** None significant. The plan was followed closely.

- **Issues encountered:**
  - Skill SKILL.md files needed to be re-applied in the final session after context compression lost the changes from an earlier session.
  - Pre-existing test failures in `test_setup_git.sh` (tests 3 and 5) were confirmed to exist before this change and are unrelated.

- **Key decisions:**
  - Child task IDs do NOT use the atomic counter (they use local scan) because parent's "Implementing" status acts as a soft lock ensuring only one PC works on children at a time.
  - When the atomic counter is unavailable (no network, no `aitask-ids` branch), the system falls back to the old local-scan approach with a warning. This preserves backward compatibility.
  - The `--commit` flag on `aitask_create.sh` auto-finalizes immediately, preserving backward compat for existing scripts.
