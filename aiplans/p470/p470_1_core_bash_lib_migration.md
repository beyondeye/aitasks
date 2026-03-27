---
Task: t470_1_core_bash_lib_migration.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_2_*.md, aitasks/t470/t470_3_*.md, aitasks/t470/t470_4_*.md, aitasks/t470/t470_5_*.md, aitasks/t470/t470_6_*.md, aitasks/t470/t470_7_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_1: Core Bash Library Migration

## Overview
Migrate `archive_utils.sh` and `archive_scan.sh` from tar.gz to tar.zst using pipe approach. Add backward compatibility fallback. Update corresponding tests.

## Step 1: Add internal helper functions to archive_utils.sh

Add format-aware helpers near the top of the file (after the guard and sourcing):

```bash
# --- Format-aware archive helpers (auto-detect by extension) ---

_archive_list() {
    local archive="$1"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" 2>/dev/null | tar -tf -
    else
        tar -tzf "$archive" 2>/dev/null
    fi
}

_archive_extract_file() {
    local archive="$1" filename="$2"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -xf - -O "$filename"
    else
        tar -xzf "$archive" -O "$filename"
    fi
}

_archive_extract_all() {
    local archive="$1" target_dir="$2"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -xf - -C "$target_dir"
    else
        tar -xzf "$archive" -C "$target_dir"
    fi
}

_archive_create() {
    local archive="$1" source_dir="$2"
    tar -cf - -C "$source_dir" . | zstd -q -o "$archive"
}

_archive_verify() {
    local archive="$1"
    if [[ "$archive" == *.tar.zst ]]; then
        zstd -dc "$archive" | tar -tf - > /dev/null
    else
        tar -tzf "$archive" > /dev/null 2>&1
    fi
}
```

## Step 2: Update archive_path_for_id()

Change the return value from `.tar.gz` to `.tar.zst`:
```bash
# Before:
echo "${archived_dir}/_b${dir}/old${bundle}.tar.gz"
# After:
echo "${archived_dir}/_b${dir}/old${bundle}.tar.zst"
```

## Step 3: Rename and update _search_tar_gz() → _search_archive()

Replace direct tar command with helper:
```bash
_search_archive() {
    local archive="$1" pattern="$2"
    _archive_list "$archive" | grep -E "$pattern"
}
```

## Step 4: Rename and update _extract_from_tar_gz() → _extract_from_archive()

Replace direct tar command with helper. Preserve the critical `_AIT_EXTRACT_RESULT` and `_AIT_ARCHIVE_TMPDIR` pattern:
```bash
_extract_from_archive() {
    local archive="$1" filename="$2"
    _AIT_ARCHIVE_TMPDIR=$(mktemp -d "${TMPDIR:-/tmp}/ait_archive_XXXXXX")
    _AIT_EXTRACT_RESULT="$_AIT_ARCHIVE_TMPDIR/$(basename "$filename")"
    _archive_extract_file "$archive" "$filename" > "$_AIT_EXTRACT_RESULT"
}
```

## Step 5: Update _find_archive_for_task()

Try `.tar.zst` first, fall back to `.tar.gz`:
```bash
_find_archive_for_task() {
    local task_id="$1" archived_dir="$2"
    local zst_path gz_path
    zst_path=$(archive_path_for_id "$task_id" "$archived_dir")
    if [[ -f "$zst_path" ]]; then
        echo "$zst_path"; return
    fi
    gz_path="${zst_path%.tar.zst}.tar.gz"
    if [[ -f "$gz_path" ]]; then
        echo "$gz_path"; return
    fi
}
```

## Step 6: Update _search_all_archives()

Change glob to search both formats:
```bash
# Search .tar.zst first, then .tar.gz
for archive in "$archived_dir"/_b*/old*.tar.zst "$archived_dir"/_b*/old*.tar.gz; do
    [[ -f "$archive" ]] || continue
    # Skip .tar.gz if corresponding .tar.zst exists
    if [[ "$archive" == *.tar.gz ]]; then
        local zst_variant="${archive%.tar.gz}.tar.zst"
        [[ -f "$zst_variant" ]] && continue
    fi
    ...
done
```

## Step 7: Update _search_numbered_then_legacy()

Try .tar.zst first at computed path, then .tar.gz variant, then legacy:
```bash
local zst_path gz_path
zst_path=$(archive_path_for_id "$task_id" "$archived_dir")
if [[ -f "$zst_path" ]]; then
    result=$(_search_archive "$zst_path" "$pattern")
    ...
fi
gz_path="${zst_path%.tar.zst}.tar.gz"
if [[ -f "$gz_path" ]]; then
    result=$(_search_archive "$gz_path" "$pattern")
    ...
fi
# Legacy fallback
for legacy in "$archived_dir/old.tar.zst" "$archived_dir/old.tar.gz"; do
    [[ -f "$legacy" ]] || continue
    result=$(_search_archive "$legacy" "$pattern")
    ...
done
```

## Step 8: Update archive_scan.sh

### scan_max_task_id()
- Change glob from `_b*/old*.tar.gz` to iterate both `.tar.zst` and `.tar.gz` (with dedup)
- Replace direct `tar -tzf` calls with `_archive_list()`
- Update legacy fallback to try `old.tar.zst` first, then `old.tar.gz`

### search_archived_task()
- Use `_search_archive()` instead of `_search_tar_gz()`
- Change output prefix from `ARCHIVED_TASK_TAR_GZ:` to `ARCHIVED_TASK_ARCHIVE:`
- Update fallback paths

### iter_all_archived_files()
- Change glob to both formats with dedup
- Replace `tar -tzf` with `_archive_list()`
- Update legacy fallback

## Step 9: Update tests/test_archive_utils.sh

### Update create_test_archive() helper
```bash
create_test_archive() {
    local archive_path="$1" source_dir="$2"
    tar -cf - -C "$source_dir" . | zstd -q -o "$archive_path"
}
```

### Keep old helper for backward compat tests
```bash
create_test_archive_gz() {
    local archive_path="$1" source_dir="$2"
    tar -czf "$archive_path" -C "$source_dir" .
}
```

### Update all test assertions
- Path assertions: `.tar.gz` → `.tar.zst`
- Add Group K: backward compat test — create `.tar.gz`, verify `_search_archive()` and `_extract_from_archive()` can read it

## Step 10: Update tests/test_archive_scan.sh

- Update fixture creation to `.tar.zst`
- Update `ARCHIVED_TASK_TAR_GZ:` assertions → `ARCHIVED_TASK_ARCHIVE:`
- Update glob expectations

## Step 11: Verify

```bash
bash tests/test_archive_utils.sh
bash tests/test_archive_scan.sh
shellcheck .aitask-scripts/lib/archive_utils.sh .aitask-scripts/lib/archive_scan.sh
```

## Step 9 Reference
Post-implementation: user review, commit, archive task, push.
