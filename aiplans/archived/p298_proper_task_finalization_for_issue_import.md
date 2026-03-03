---
Task: t298_proper_task_finalization_for_issue_import.md
Worktree: N/A (current branch)
Branch: main
Base branch: main
---

# Plan: Fix task finalization for issue-import (t298)

## Context

The `aitask_issue_import.sh` script has a broken task finalization flow in interactive mode. When importing an issue interactively, it:
1. Creates the task via `aitask_create.sh --batch` (which creates a **draft** in `aitasks/new/`)
2. Then does manual `git add` + `git commit` on the draft file — but the file is still a draft without a real task ID

This was the same bug fixed in `aitask_pr_import.sh` (commit fcdfa3b, t295). The pr-import fix introduced a draft/finalize choice **before** calling `aitask_create.sh`, passing `--commit` to let `aitask_create.sh` handle proper task ID claiming and finalization internally.

## Changes

**File: `aiscripts/aitask_issue_import.sh`**

### 1. Interactive mode (`interactive_import_issue`, lines 722-748)

**Replace** the current post-creation git handling with the pr-import pattern:

- **Before creating the task** (after line 728, before calling `aitask_create.sh`): Add the draft/finalize fzf prompt:
  ```bash
  local save_action
  save_action=$(printf "Finalize and commit (assign real task ID and commit)\nSave as draft (keep in aitasks/new/ for later finalization)" | \
      fzf --prompt="How to save? " --height=8 --no-info \
      --header="Finalize claims a real task ID and commits to git")
  [[ -z "$save_action" ]] && save_action="Save as draft"
  if [[ "$save_action" == "Finalize and commit"* ]]; then
      create_args+=(--commit)
  fi
  ```

- **After task creation**: Replace the manual git operations (lines 734-748) with proper success messages:
  ```bash
  local created_file
  created_file="${result#Created: }"
  if [[ "$save_action" == "Finalize and commit"* ]]; then
      success "Finalized and committed: $created_file"
  else
      success "Draft saved: $created_file"
      info "Finalize later with: ait create (interactive) or --batch --finalize <file>"
  fi
  ```

This removes the broken manual `git add`/`git commit`/`read -rp "Commit to git?"` block and replaces it with the `--commit` flag approach that delegates to `aitask_create.sh`'s proper finalization (which uses `claim_next_task_id`, `task_git`, proper file renaming).

### 2. Batch mode — already correct

The batch mode (`import_single_issue`, line 486) already passes `--commit` conditionally:
```bash
[[ "$BATCH_COMMIT" == true ]] && create_args+=(--commit)
```
No changes needed in batch mode.

## Verification

1. Run `shellcheck aiscripts/aitask_issue_import.sh` — should pass
2. Compare the interactive finalization logic side-by-side with `aitask_pr_import.sh` lines 1275-1297 to confirm they match
3. Manual test (if GitHub CLI available): `./aiscripts/aitask_issue_import.sh` — verify the draft/finalize prompt appears and both options work correctly

## Final Implementation Notes
- **Actual work done:** Replaced the broken post-creation manual git handling in `interactive_import_issue()` with the pre-creation draft/finalize pattern from `aitask_pr_import.sh`. The key change is adding a fzf prompt before calling `aitask_create.sh` and passing `--commit` conditionally, removing the manual `git add`/`git commit` block.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None. Shellcheck passes with only pre-existing warnings (SC1091, SC2034, SC2059).
- **Key decisions:** Kept the implementation identical to the pr-import pattern for consistency, including the same fzf prompt text and default behavior (defaults to "Save as draft" if user cancels fzf).
