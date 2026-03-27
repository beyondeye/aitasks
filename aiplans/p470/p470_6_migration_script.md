---
Task: t470_6_migration_script.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_2_*.md, aitasks/t470/t470_3_*.md
Archived Sibling Plans: aiplans/archived/p470/p470_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_6: Migration Script

## Overview
Create a standalone script that converts existing `old*.tar.gz` archives to `old*.tar.zst` format. Add as `ait migrate-archives` subcommand.

## Step 1: Create .aitask-scripts/aitask_migrate_archives.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

# Source utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/terminal_compat.sh"

# Defaults
DRY_RUN=false
DELETE_OLD=false
VERBOSE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --delete-old) DELETE_OLD=true; shift ;;
        --verbose) VERBOSE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown argument: $1" ;;
    esac
done

# Scan directories
TASK_ARCHIVED="${TASK_DIR:-aitasks}/archived"
PLAN_ARCHIVED="${PLAN_DIR:-aiplans}/archived"

# Core conversion logic per archive
convert_archive() {
    local gz_path="$1"
    local zst_path="${gz_path%.tar.gz}.tar.zst"

    if [[ -f "$zst_path" ]]; then
        $VERBOSE && info "Skipping $gz_path (already converted)"
        return 1  # skipped
    fi

    if $DRY_RUN; then
        info "Would convert: $gz_path → $zst_path"
        return 0
    fi

    local temp_dir
    temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/ait_migrate_XXXXXX")
    trap "rm -rf '$temp_dir'" RETURN

    tar -xzf "$gz_path" -C "$temp_dir"
    tar -cf - -C "$temp_dir" . | zstd -q -o "$zst_path"

    # Verify
    zstd -dc "$zst_path" | tar -tf - > /dev/null

    $VERBOSE && info "Converted: $gz_path → $zst_path"

    if $DELETE_OLD; then
        rm -f "$gz_path"
        $VERBOSE && info "Deleted: $gz_path"
    fi
}

# Main: scan and convert
```

## Step 2: Scan logic

Find all tar.gz archives in both task and plan archived directories:
- `${TASK_ARCHIVED}/_b*/old*.tar.gz`
- `${PLAN_ARCHIVED}/_b*/old*.tar.gz`
- `${TASK_ARCHIVED}/old.tar.gz` (legacy)
- `${PLAN_ARCHIVED}/old.tar.gz` (legacy)

## Step 3: Summary output

Print: total found, converted, skipped, failed.

## Step 4: Add to ait dispatcher

Add `migrate-archives` case to the main `ait` dispatcher script.

## Step 5: Verify

```bash
shellcheck .aitask-scripts/aitask_migrate_archives.sh
./ait migrate-archives --dry-run  # preview
```

## Step 9 Reference
Post-implementation: user review, commit, archive task, push.
