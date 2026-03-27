---
Task: t470_3_zip_old_and_create_migration.md
Parent Task: aitasks/t470_migrate_archive_format_tar_gz_to_tar_zst.md
Sibling Tasks: aitasks/t470/t470_1_*.md, aitasks/t470/t470_2_*.md
Archived Sibling Plans: aiplans/archived/p470/p470_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# t470_3: aitask_zip_old.sh + aitask_create.sh Migration

## Overview
Update the archive creation/management script and task creation script to produce and consume tar.zst archives. This is the only script that CREATES archives.

## Step 1: Update _archive_single_bundle() in aitask_zip_old.sh

This function creates or merges archive bundles (lines ~226-281):

- **Line 239 (extract existing):**
  ```bash
  # Before: tar -xzf "$archive_path" -C "$temp_dir"
  # After: use _archive_extract_all helper
  _archive_extract_all "$archive_path" "$temp_dir"
  ```

- **Line 261 (create archive):**
  ```bash
  # Before: tar -czf "$archive_path" -C "$temp_dir" .
  # After:
  tar -cf - -C "$temp_dir" . | zstd -q -o "$archive_path"
  ```

- **Line 262 (verify):**
  ```bash
  # Before: tar -tzf "$archive_path" > /dev/null 2>&1
  # After:
  _archive_verify "$archive_path"
  ```

Note: `archive_path_for_id()` already returns `.tar.zst` after t470_1, so new archives will be created as `.tar.zst`. The extract line uses `_archive_extract_all()` which auto-detects format, so it can extract existing `.tar.gz` archives during the transition period.

## Step 2: Update cmd_unpack() in aitask_zip_old.sh

Unpack subcommand (lines ~372-440):

- **Line 395 (list contents):**
  ```bash
  # Before: tar -tzf "$arch" 2>/dev/null | grep -E ...
  # After:
  _archive_list "$arch" | grep -E ...
  ```

- **Line 401 (extract all):**
  ```bash
  # Before: tar -xzf "$arch" -C "$temp_dir"
  # After:
  _archive_extract_all "$arch" "$temp_dir"
  ```

- **Line 429 (rebuild after removal):**
  ```bash
  # Before: tar -czf "$arch" -C "$temp_dir" .
  # After: always create as .tar.zst
  local new_arch="${arch%.tar.gz}"  # strip .tar.gz if present
  new_arch="${new_arch%.tar.zst}.tar.zst"  # ensure .tar.zst
  tar -cf - -C "$temp_dir" . | zstd -q -o "$new_arch"
  # If format changed, remove old file
  [[ "$arch" != "$new_arch" ]] && rm -f "$arch"
  ```

- **Lines 370/387 (legacy fallback):** try `old.tar.zst` first, fall back to `old.tar.gz`

## Step 3: Update git staging globs

Lines ~532-533:
```bash
# Before: _b*/old*.tar.gz
# After: _b*/old*.tar.zst
# Also stage .tar.gz removals if any
```

## Step 4: Update comments and help text

- Line 4, 9, 50: numbering scheme comments → `.tar.zst`
- Help/usage text: update format references

## Step 5: Update aitask_create.sh

- **Line 15:** `ARCHIVE_FILE` — try `.tar.zst` first:
  ```bash
  if [[ -f "aitasks/archived/old.tar.zst" ]]; then
      ARCHIVE_FILE="aitasks/archived/old.tar.zst"
  elif [[ -f "aitasks/archived/old.tar.gz" ]]; then
      ARCHIVE_FILE="aitasks/archived/old.tar.gz"
  else
      ARCHIVE_FILE=""
  fi
  ```

- **Lines 191, 663:** Replace `tar -tzf` with `_archive_list()`:
  ```bash
  # Before: tar -tzf "$ARCHIVE_FILE" 2>/dev/null | grep -E ...
  # After:
  _archive_list "$ARCHIVE_FILE" | grep -E ...
  ```

## Step 6: Update tests/test_zip_old.sh (26 tests)

### Update test helper for archive creation
All fixture creation that uses `tar -czf` → pipe approach creating `.tar.zst`

### Update verification commands
All `tar -tzf` verification → `_archive_list()` or `zstd -dc | tar -tf -`

### Update path assertions
- `.tar.gz` → `.tar.zst` in file existence checks
- Test 9: verify `_b0/old0.tar.zst` exists
- Test 10: cumulative archiving creates `.tar.zst`
- Tests 20-26: unpack from `.tar.zst`
- Test 25: archive deleted when emptied → `.tar.zst`

### Git glob assertions
- `_b*/old*.tar.gz` → `_b*/old*.tar.zst`

## Step 7: Verify

```bash
bash tests/test_zip_old.sh
shellcheck .aitask-scripts/aitask_zip_old.sh .aitask-scripts/aitask_create.sh
```

## Step 9 Reference
Post-implementation: user review, commit, archive task, push.
