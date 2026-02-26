---
priority: high
effort: medium
depends: [t259_3]
issue_type: feature
status: Ready
labels: [aitask_review]
created_at: 2026-02-26 18:43
updated_at: 2026-02-26 18:43
---

## Context

This task creates bash management scripts for review run data, mirroring the aitask_explain_runs.sh and aitask_explain_cleanup.sh scripts used for aiexplains data. These scripts provide list, delete, cleanup, and info operations for the aireviews/ directory.

The directory naming convention is <dir_key>__<YYYYMMDD_HHMMSS> where dir_key encodes the source directory path (same as aiexplains/).

## Key Files to Modify

- aiscripts/aitask_review_runs.sh (new) — list, delete, info for review runs
- aiscripts/aitask_review_cleanup.sh (new) — cleanup stale runs (keep newest per key)
- ait — add review-runs and review-cleanup commands to dispatcher

## Reference Files for Patterns

- aiscripts/aitask_explain_runs.sh — primary pattern for list/delete/info
- aiscripts/aitask_explain_cleanup.sh — primary pattern for cleanup algorithm
- aiscripts/lib/terminal_compat.sh — portability helpers

## Implementation Plan

### Step 1: Create aitask_review_cleanup.sh

Mirror aitask_explain_cleanup.sh:
- Default target: aireviews/
- Marker validation: check for manifest.yaml
- Options: --target DIR, --dry-run, --quiet
- Algorithm: group by dir_key, find newest per key, remove older
- Safety: realpath validation
- Output: CLEANED: <count>

### Step 2: Create aitask_review_runs.sh

Mirror aitask_explain_runs.sh:
- --list: all runs with dir_key, timestamp, status, file count, finding count
- --info <run_dir>: detailed manifest info
- --delete <run_dir>: delete with realpath safety
- --delete-all: remove all runs
- --cleanup-stale: delegate to aitask_review_cleanup.sh
- Interactive (no args): fzf selection with manifest preview

### Step 3: Add ait dispatcher commands

Add to ait case statement:
  review-runs)    shift; exec SCRIPTS_DIR/aitask_review_runs.sh
  review-cleanup) shift; exec SCRIPTS_DIR/aitask_review_cleanup.sh

## Verification Steps

- shellcheck aiscripts/aitask_review_runs.sh aiscripts/aitask_review_cleanup.sh
- Create sample run dirs with manifest.yaml, test list/cleanup/delete
