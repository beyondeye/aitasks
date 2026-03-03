---
Task: t295_fix_pr_import_interactive_mode.md
Branch: (current branch)
Base branch: main
---

# Plan: Fix PR Import Interactive Mode (t295)

## Context

The interactive mode of `aiscripts/aitask_pr_import.sh` has a critical bug: it calls `aitask_create.sh --batch` **without** `--commit`, creating drafts in `aitasks/new/` instead of finalized tasks. The manual "Commit to git?" prompt then commits the draft file as-is — no real task ID is assigned. Additionally, it uses plain `git` instead of `task_git`, and lacks informational notes about the code agent skill alternative (`/aitask-pr-review`).

## Changes

### File: `aiscripts/aitask_pr_import.sh`

#### 1. Add skill recommendation note in `run_interactive_mode()` (line ~1315)

After the fzf/CLI checks, before the mode selection fzf prompt, add an `info` message.

#### 2. Improve import confirmation prompt in `interactive_import_pr()` (line ~1049)

Replace the fzf options with descriptive labels and add an explanatory header.

#### 3. Add skill advantages tip after "Import" is chosen (after line ~1068)

After confirming import (before the task name prompt), print a brief note about what the code agent skill provides.

#### 4. Fix the end flow — replace draft+manual-commit with proper finalize (lines ~1216-1244)

Replace the broken manual `git add`/`git commit` block with an fzf prompt that controls whether `--commit` is passed to `aitask_create.sh`. When `--commit` is passed, `aitask_create.sh` handles ID claiming, file placement in `aitasks/`, and git commit using `task_git` internally.

## Verification

1. Run `shellcheck aiscripts/aitask_pr_import.sh` for lint
2. Verify the info note about `/aitask-pr-review` appears at the start of interactive mode
3. Verify the improved fzf prompts have descriptive labels
4. Verify "Finalize and commit" creates a real task in `aitasks/` (not `aitasks/new/`)

## Final Implementation Notes
- **Actual work done:** All 4 changes implemented as planned. No deviations.
- **Deviations from plan:** None. The simplified two-option approach (Finalize and commit / Save as draft) was used as planned.
- **Issues encountered:** None. shellcheck passed with only pre-existing warnings (SC1091, SC2046).
- **Key decisions:** Kept the end flow to two options instead of three — "Finalize without commit" was excluded since `finalize_draft` is defined in `aitask_create.sh` (not available in `pr_import.sh`).
