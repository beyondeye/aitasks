---
priority: high
effort: medium
depends: [t259_1]
issue_type: feature
status: Ready
labels: [aitask_review]
created_at: 2026-02-26 18:42
updated_at: 2026-02-26 18:42
---

## Context

This is the core batch driver script for the batch review system (t259). It handles file/directory selection, file discovery, partitioning into batches, and run directory setup. The Claude session orchestration (t259_3) extends this script.

The run directory naming follows the aiexplains/ convention: <dir_key>__<YYYYMMDD_HHMMSS> stored under aireviews/.

## Key Files to Modify

- aiscripts/aitask_review_batch_run.sh (new) — main batch driver script

## Reference Files for Patterns

- aiscripts/aitask_create.sh — pattern for dual interactive/batch mode with --batch flag
- aiscripts/aitask_explain_extract_raw_data.sh — pattern for dir_to_key() function, run directory creation
- aiscripts/aitask_review_detect_env.sh — reuse for environment detection and guide ranking
- aiscripts/lib/terminal_compat.sh — source for portability helpers
- aiscripts/lib/task_utils.sh — source for shared utilities

## Implementation Plan

### Step 1: Script skeleton with argument parsing

Create aiscripts/aitask_review_batch_run.sh with:
- Shebang, set -euo pipefail, source libs
- show_help() with full usage
- Arg parsing: --batch --targets --source-root --guides --max-parallel --timeout --max-files-per-session --model --output-dir
- Defaults: MAX_PARALLEL=3, TIMEOUT=600, MAX_FILES_PER_SESSION=5, MODEL=sonnet

### Step 2: File/directory selection (interactive mode)

- fzf-based target selection, support external paths
- Support selecting multiple files/directories

### Step 3: File discovery and expansion

- git ls-files for git repos, find for external paths
- Filter binary files, build artifacts, node_modules
- Report total file count

### Step 4: Review guide selection

- Interactive: aitask_review_detect_env.sh --files-stdin, fzf multi-select
- Batch: parse --guides comma-separated, verify paths in aireviewguides/

### Step 5: File partitioning

- Group by extension/language
- Split respecting --max-files-per-session and 50KB size limit
- Large files (>20KB) get own session

### Step 6: Run directory creation

- dir_to_key(): / -> __, root -> _root_, external -> _ext prefix
- Create aireviews/<dir_key>__<timestamp>/findings/
- Write initial manifest.yaml with status: running
- Print RUN_DIR: <path>

### Step 7: Auto-cleanup after run directory creation

## Verification Steps

- shellcheck aiscripts/aitask_review_batch_run.sh
- Test interactive and batch modes
- Test with external directory path
